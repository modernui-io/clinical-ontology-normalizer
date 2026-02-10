"""Country-Level Regulatory Requirements Service (REG-COUNTRY).

Manages country-specific regulatory requirements, ethics committee submissions,
import/export licenses, local regulatory agent assignments, country activation
tracking, and regulatory compliance metrics per jurisdiction.

Usage:
    from app.services.country_regulatory_service import (
        get_country_regulatory_service,
    )

    svc = get_country_regulatory_service()
    requirements = svc.list_requirements()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.country_regulatory import (
    ActivationStatus,
    AgentRole,
    ApprovalStatus,
    CountryActivation,
    CountryActivationCreate,
    CountryActivationUpdate,
    CountryRegulatoryMetrics,
    CountryRequirement,
    CountryRequirementCreate,
    CountryRequirementUpdate,
    EthicsSubmission,
    EthicsSubmissionCreate,
    EthicsSubmissionUpdate,
    ImportExportLicense,
    ImportExportLicenseCreate,
    ImportExportLicenseUpdate,
    LocalAgent,
    LocalAgentCreate,
    LocalAgentUpdate,
    SubmissionType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CountryRegulatoryService:
    """In-memory Country-Level Regulatory Requirements engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._requirements: dict[str, CountryRequirement] = {}
        self._ethics: dict[str, EthicsSubmission] = {}
        self._licenses: dict[str, ImportExportLicense] = {}
        self._agents: dict[str, LocalAgent] = {}
        self._activations: dict[str, CountryActivation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic country regulatory data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Country Requirements ---
        requirements_data = [
            {"id": "CREQ-001", "trial_id": EYLEA_TRIAL, "country": "United States", "country_code": "US", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "FDA IND submission for EYLEA HD Phase III", "regulatory_authority": "FDA", "submission_deadline": now - timedelta(days=180), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=200), "approval_date": now - timedelta(days=160), "approval_reference": "IND-2024-78432", "conditions": [], "documents_required": ["IND application", "Protocol", "IB", "CMC data"], "responsible_person": "Dr. Sarah Mitchell", "created_at": now - timedelta(days=220)},
            {"id": "CREQ-002", "trial_id": EYLEA_TRIAL, "country": "United Kingdom", "country_code": "GB", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "MHRA CTA submission for EYLEA HD", "regulatory_authority": "MHRA", "submission_deadline": now - timedelta(days=150), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=170), "approval_date": now - timedelta(days=130), "approval_reference": "CTA-2024-11205", "conditions": ["Annual safety reports required"], "documents_required": ["CTA form", "IMPD", "Protocol", "IB"], "responsible_person": "Dr. James Clarke", "created_at": now - timedelta(days=190)},
            {"id": "CREQ-003", "trial_id": EYLEA_TRIAL, "country": "Germany", "country_code": "DE", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "BfArM CTA submission for EYLEA HD", "regulatory_authority": "BfArM", "submission_deadline": now - timedelta(days=140), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=160), "approval_date": now - timedelta(days=120), "approval_reference": "CTA-DE-2024-3398", "conditions": ["GMP certificate required for local depot"], "documents_required": ["EU CTA form", "IMPD", "Protocol", "IB", "GMP certificate"], "responsible_person": "Dr. Klaus Weber", "created_at": now - timedelta(days=180)},
            {"id": "CREQ-004", "trial_id": EYLEA_TRIAL, "country": "Japan", "country_code": "JP", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "PMDA CTN submission for EYLEA HD", "regulatory_authority": "PMDA", "submission_deadline": now - timedelta(days=120), "approval_status": ApprovalStatus.CONDITIONALLY_APPROVED, "submission_date": now - timedelta(days=140), "approval_date": now - timedelta(days=100), "approval_reference": "CTN-JP-2024-5567", "conditions": ["Japanese patient population requirement", "Local labeling compliance"], "documents_required": ["CTN form", "J-IND", "Protocol (Japanese)", "IB"], "responsible_person": "Dr. Yuki Tanaka", "created_at": now - timedelta(days=160)},
            {"id": "CREQ-005", "trial_id": DUPIXENT_TRIAL, "country": "United States", "country_code": "US", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "FDA IND amendment for Dupixent COPD indication", "regulatory_authority": "FDA", "submission_deadline": now - timedelta(days=160), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=180), "approval_date": now - timedelta(days=140), "approval_reference": "IND-2024-92110", "conditions": [], "documents_required": ["IND amendment", "Updated protocol", "IB supplement"], "responsible_person": "Dr. Maria Rodriguez", "created_at": now - timedelta(days=200)},
            {"id": "CREQ-006", "trial_id": DUPIXENT_TRIAL, "country": "France", "country_code": "FR", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "ANSM CTA for Dupixent COPD", "regulatory_authority": "ANSM", "submission_deadline": now - timedelta(days=130), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=150), "approval_date": now - timedelta(days=110), "approval_reference": "CTA-FR-2024-7821", "conditions": [], "documents_required": ["EU CTA form", "IMPD", "Protocol (French)", "IB"], "responsible_person": "Dr. Pierre Dubois", "created_at": now - timedelta(days=170)},
            {"id": "CREQ-007", "trial_id": DUPIXENT_TRIAL, "country": "Brazil", "country_code": "BR", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "ANVISA CTA for Dupixent COPD", "regulatory_authority": "ANVISA", "submission_deadline": now - timedelta(days=90), "approval_status": ApprovalStatus.UNDER_REVIEW, "submission_date": now - timedelta(days=100), "approval_date": None, "approval_reference": None, "conditions": [], "documents_required": ["ANVISA form", "Protocol (Portuguese)", "IB", "ICF (Portuguese)"], "responsible_person": "Dr. Ana Silva", "created_at": now - timedelta(days=120)},
            {"id": "CREQ-008", "trial_id": DUPIXENT_TRIAL, "country": "South Korea", "country_code": "KR", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "MFDS CTA for Dupixent COPD", "regulatory_authority": "MFDS", "submission_deadline": now - timedelta(days=100), "approval_status": ApprovalStatus.SUBMITTED, "submission_date": now - timedelta(days=110), "approval_date": None, "approval_reference": None, "conditions": [], "documents_required": ["MFDS CTA form", "Protocol (Korean)", "IB", "ICF (Korean)"], "responsible_person": "Dr. Min-Jun Park", "created_at": now - timedelta(days=130)},
            {"id": "CREQ-009", "trial_id": LIBTAYO_TRIAL, "country": "United States", "country_code": "US", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "FDA IND for Libtayo combination therapy", "regulatory_authority": "FDA", "submission_deadline": now - timedelta(days=200), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=220), "approval_date": now - timedelta(days=180), "approval_reference": "IND-2024-65789", "conditions": [], "documents_required": ["IND application", "Protocol", "IB", "CMC data"], "responsible_person": "Dr. Robert Chang", "created_at": now - timedelta(days=240)},
            {"id": "CREQ-010", "trial_id": LIBTAYO_TRIAL, "country": "Australia", "country_code": "AU", "requirement_type": SubmissionType.REGULATORY_AUTHORITY, "description": "TGA CTN for Libtayo combination therapy", "regulatory_authority": "TGA", "submission_deadline": now - timedelta(days=140), "approval_status": ApprovalStatus.APPROVED, "submission_date": now - timedelta(days=160), "approval_date": now - timedelta(days=120), "approval_reference": "CTN-AU-2024-4412", "conditions": [], "documents_required": ["CTN form", "Protocol", "IB"], "responsible_person": "Dr. Emily Watson", "created_at": now - timedelta(days=180)},
            {"id": "CREQ-011", "trial_id": LIBTAYO_TRIAL, "country": "Canada", "country_code": "CA", "requirement_type": SubmissionType.SAFETY_REPORTING, "description": "Health Canada safety reporting requirements for Libtayo", "regulatory_authority": "Health Canada", "submission_deadline": now - timedelta(days=60), "approval_status": ApprovalStatus.NOT_SUBMITTED, "submission_date": None, "approval_date": None, "approval_reference": None, "conditions": [], "documents_required": ["Safety reporting plan", "DSUR template"], "responsible_person": "Dr. Nicole Tremblay", "created_at": now - timedelta(days=80)},
            {"id": "CREQ-012", "trial_id": EYLEA_TRIAL, "country": "India", "country_code": "IN", "requirement_type": SubmissionType.LOCAL_LABELING, "description": "CDSCO local labeling requirements for EYLEA HD", "regulatory_authority": "CDSCO", "submission_deadline": now - timedelta(days=30), "approval_status": ApprovalStatus.REJECTED, "submission_date": now - timedelta(days=50), "approval_date": None, "approval_reference": None, "conditions": ["Labeling does not comply with local language requirements"], "documents_required": ["Local labeling dossier", "Translation certificates"], "responsible_person": "Dr. Priya Sharma", "created_at": now - timedelta(days=70)},
        ]

        for r in requirements_data:
            self._requirements[r["id"]] = CountryRequirement(**r)

        # --- 10 Ethics Submissions ---
        ethics_data = [
            {"id": "ETH-001", "trial_id": EYLEA_TRIAL, "country": "United States", "committee_name": "Western IRB (WCG)", "submission_date": now - timedelta(days=210), "protocol_version": "3.0", "icf_version": "2.1", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=190), "approval_reference": "IRB-2024-EYLEA-001", "expiry_date": now + timedelta(days=175), "conditions": [], "annual_renewal_due": now + timedelta(days=175), "submitted_by": "Dr. Sarah Mitchell"},
            {"id": "ETH-002", "trial_id": EYLEA_TRIAL, "country": "United Kingdom", "committee_name": "NHS Health Research Authority", "submission_date": now - timedelta(days=180), "protocol_version": "3.0", "icf_version": "2.0", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=155), "approval_reference": "HRA-2024-EYLEA-GB", "expiry_date": now + timedelta(days=210), "conditions": ["Patient information sheet update required"], "annual_renewal_due": now + timedelta(days=210), "submitted_by": "Dr. James Clarke"},
            {"id": "ETH-003", "trial_id": EYLEA_TRIAL, "country": "Germany", "committee_name": "Ethikkommission der Universitat Heidelberg", "submission_date": now - timedelta(days=170), "protocol_version": "3.0", "icf_version": "2.0-DE", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=140), "approval_reference": "EC-HD-2024-EYLEA", "expiry_date": now + timedelta(days=225), "conditions": [], "annual_renewal_due": now + timedelta(days=225), "submitted_by": "Dr. Klaus Weber"},
            {"id": "ETH-004", "trial_id": EYLEA_TRIAL, "country": "Japan", "committee_name": "National Center for Global Health and Medicine IRB", "submission_date": now - timedelta(days=150), "protocol_version": "3.0", "icf_version": "2.0-JP", "approval_status": ApprovalStatus.CONDITIONALLY_APPROVED, "approval_date": now - timedelta(days=120), "approval_reference": "IRB-NCGM-2024-EYLEA", "expiry_date": now + timedelta(days=245), "conditions": ["Additional genetic consent form required"], "annual_renewal_due": now + timedelta(days=245), "submitted_by": "Dr. Yuki Tanaka"},
            {"id": "ETH-005", "trial_id": DUPIXENT_TRIAL, "country": "United States", "committee_name": "Advarra IRB", "submission_date": now - timedelta(days=190), "protocol_version": "2.0", "icf_version": "1.5", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=165), "approval_reference": "ADV-2024-DUP-001", "expiry_date": now + timedelta(days=200), "conditions": [], "annual_renewal_due": now + timedelta(days=200), "submitted_by": "Dr. Maria Rodriguez"},
            {"id": "ETH-006", "trial_id": DUPIXENT_TRIAL, "country": "France", "committee_name": "Comite de Protection des Personnes Ile-de-France", "submission_date": now - timedelta(days=160), "protocol_version": "2.0", "icf_version": "1.5-FR", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=130), "approval_reference": "CPP-IDF-2024-DUP", "expiry_date": now + timedelta(days=235), "conditions": [], "annual_renewal_due": now + timedelta(days=235), "submitted_by": "Dr. Pierre Dubois"},
            {"id": "ETH-007", "trial_id": DUPIXENT_TRIAL, "country": "Brazil", "committee_name": "CEP Hospital das Clinicas USP", "submission_date": now - timedelta(days=110), "protocol_version": "2.0", "icf_version": "1.5-BR", "approval_status": ApprovalStatus.UNDER_REVIEW, "approval_date": None, "approval_reference": None, "expiry_date": None, "conditions": [], "annual_renewal_due": None, "submitted_by": "Dr. Ana Silva"},
            {"id": "ETH-008", "trial_id": LIBTAYO_TRIAL, "country": "United States", "committee_name": "WIRB-Copernicus Group", "submission_date": now - timedelta(days=230), "protocol_version": "4.0", "icf_version": "3.0", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=210), "approval_reference": "WCG-2024-LIB-001", "expiry_date": now + timedelta(days=155), "conditions": [], "annual_renewal_due": now + timedelta(days=155), "submitted_by": "Dr. Robert Chang"},
            {"id": "ETH-009", "trial_id": LIBTAYO_TRIAL, "country": "Australia", "committee_name": "Melbourne Health HREC", "submission_date": now - timedelta(days=170), "protocol_version": "4.0", "icf_version": "3.0-AU", "approval_status": ApprovalStatus.APPROVED, "approval_date": now - timedelta(days=145), "approval_reference": "HREC-MH-2024-LIB", "expiry_date": now + timedelta(days=220), "conditions": [], "annual_renewal_due": now + timedelta(days=220), "submitted_by": "Dr. Emily Watson"},
            {"id": "ETH-010", "trial_id": DUPIXENT_TRIAL, "country": "South Korea", "committee_name": "Seoul National University Hospital IRB", "submission_date": now - timedelta(days=115), "protocol_version": "2.0", "icf_version": "1.5-KR", "approval_status": ApprovalStatus.SUBMITTED, "approval_date": None, "approval_reference": None, "expiry_date": None, "conditions": [], "annual_renewal_due": None, "submitted_by": "Dr. Min-Jun Park"},
        ]

        for e in ethics_data:
            self._ethics[e["id"]] = EthicsSubmission(**e)

        # --- 10 Import/Export Licenses ---
        licenses_data = [
            {"id": "LIC-001", "trial_id": EYLEA_TRIAL, "country": "United Kingdom", "license_type": "import", "license_number": "IMP-GB-2024-3321", "product_name": "EYLEA HD (aflibercept 8mg)", "quantity_authorized": 500, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=175), "approval_date": now - timedelta(days=150), "expiry_date": now + timedelta(days=190), "customs_reference": "HMRC-IMP-2024-EYLEA", "responsible_person": "Dr. James Clarke"},
            {"id": "LIC-002", "trial_id": EYLEA_TRIAL, "country": "Germany", "license_type": "import", "license_number": "IMP-DE-2024-4456", "product_name": "EYLEA HD (aflibercept 8mg)", "quantity_authorized": 750, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=165), "approval_date": now - timedelta(days=135), "expiry_date": now + timedelta(days=230), "customs_reference": "ZOLL-2024-EYLEA", "responsible_person": "Dr. Klaus Weber"},
            {"id": "LIC-003", "trial_id": EYLEA_TRIAL, "country": "Japan", "license_type": "import", "license_number": "IMP-JP-2024-7789", "product_name": "EYLEA HD (aflibercept 8mg)", "quantity_authorized": 400, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=145), "approval_date": now - timedelta(days=110), "expiry_date": now + timedelta(days=255), "customs_reference": "MHLW-2024-EYLEA", "responsible_person": "Dr. Yuki Tanaka"},
            {"id": "LIC-004", "trial_id": DUPIXENT_TRIAL, "country": "France", "license_type": "import", "license_number": "IMP-FR-2024-5534", "product_name": "Dupixent (dupilumab 300mg)", "quantity_authorized": 1200, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=155), "approval_date": now - timedelta(days=125), "expiry_date": now + timedelta(days=240), "customs_reference": "DOUANES-2024-DUP", "responsible_person": "Dr. Pierre Dubois"},
            {"id": "LIC-005", "trial_id": DUPIXENT_TRIAL, "country": "Brazil", "license_type": "import", "license_number": None, "product_name": "Dupixent (dupilumab 300mg)", "quantity_authorized": 600, "status": ApprovalStatus.SUBMITTED, "application_date": now - timedelta(days=95), "approval_date": None, "expiry_date": None, "customs_reference": None, "responsible_person": "Dr. Ana Silva"},
            {"id": "LIC-006", "trial_id": DUPIXENT_TRIAL, "country": "South Korea", "license_type": "import", "license_number": None, "product_name": "Dupixent (dupilumab 300mg)", "quantity_authorized": 300, "status": ApprovalStatus.UNDER_REVIEW, "application_date": now - timedelta(days=105), "approval_date": None, "expiry_date": None, "customs_reference": None, "responsible_person": "Dr. Min-Jun Park"},
            {"id": "LIC-007", "trial_id": LIBTAYO_TRIAL, "country": "Australia", "license_type": "import", "license_number": "IMP-AU-2024-2298", "product_name": "Libtayo (cemiplimab 350mg)", "quantity_authorized": 350, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=165), "approval_date": now - timedelta(days=130), "expiry_date": now + timedelta(days=235), "customs_reference": "ABF-2024-LIB", "responsible_person": "Dr. Emily Watson"},
            {"id": "LIC-008", "trial_id": EYLEA_TRIAL, "country": "United States", "license_type": "export", "license_number": "EXP-US-2024-1001", "product_name": "EYLEA HD (aflibercept 8mg)", "quantity_authorized": 2000, "status": ApprovalStatus.APPROVED, "application_date": now - timedelta(days=200), "approval_date": now - timedelta(days=185), "expiry_date": now + timedelta(days=180), "customs_reference": "CBP-2024-EYLEA-EXP", "responsible_person": "Dr. Sarah Mitchell"},
            {"id": "LIC-009", "trial_id": LIBTAYO_TRIAL, "country": "Canada", "license_type": "import", "license_number": None, "product_name": "Libtayo (cemiplimab 350mg)", "quantity_authorized": 200, "status": ApprovalStatus.NOT_SUBMITTED, "application_date": now - timedelta(days=40), "approval_date": None, "expiry_date": None, "customs_reference": None, "responsible_person": "Dr. Nicole Tremblay"},
            {"id": "LIC-010", "trial_id": EYLEA_TRIAL, "country": "India", "license_type": "import", "license_number": None, "product_name": "EYLEA HD (aflibercept 8mg)", "quantity_authorized": 300, "status": ApprovalStatus.REJECTED, "application_date": now - timedelta(days=55), "approval_date": None, "expiry_date": None, "customs_reference": None, "responsible_person": "Dr. Priya Sharma"},
        ]

        for lic in licenses_data:
            self._licenses[lic["id"]] = ImportExportLicense(**lic)

        # --- 10 Local Agents ---
        agents_data = [
            {"id": "AGT-001", "trial_id": EYLEA_TRIAL, "country": "United Kingdom", "agent_name": "Jonathan Blackwell", "organization": "Regulatory Solutions UK Ltd", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "j.blackwell@regsolutions.co.uk", "contact_phone": "+44-20-7946-0958", "contract_start": now - timedelta(days=200), "contract_end": now + timedelta(days=165), "active": True},
            {"id": "AGT-002", "trial_id": EYLEA_TRIAL, "country": "Germany", "agent_name": "Hans Mueller", "organization": "RegAffairs GmbH", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "h.mueller@regaffairs.de", "contact_phone": "+49-30-2014-5678", "contract_start": now - timedelta(days=190), "contract_end": now + timedelta(days=175), "active": True},
            {"id": "AGT-003", "trial_id": EYLEA_TRIAL, "country": "Japan", "agent_name": "Kenji Watanabe", "organization": "Japan Clinical Regulatory Corp", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "k.watanabe@jcrc.co.jp", "contact_phone": "+81-3-1234-5678", "contract_start": now - timedelta(days=160), "contract_end": now + timedelta(days=205), "active": True},
            {"id": "AGT-004", "trial_id": DUPIXENT_TRIAL, "country": "France", "agent_name": "Marie Lefebvre", "organization": "EuroReg Consulting SARL", "role": AgentRole.LEGAL_REPRESENTATIVE, "contact_email": "m.lefebvre@euroreg.fr", "contact_phone": "+33-1-4567-8901", "contract_start": now - timedelta(days=170), "contract_end": now + timedelta(days=195), "active": True},
            {"id": "AGT-005", "trial_id": DUPIXENT_TRIAL, "country": "Brazil", "agent_name": "Carlos Oliveira", "organization": "LatAm Regulatory Partners", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "c.oliveira@latamreg.com.br", "contact_phone": "+55-11-9876-5432", "contract_start": now - timedelta(days=120), "contract_end": now + timedelta(days=245), "active": True},
            {"id": "AGT-006", "trial_id": DUPIXENT_TRIAL, "country": "South Korea", "agent_name": "Soo-Yeon Kim", "organization": "APAC Regulatory Services", "role": AgentRole.PHARMACOVIGILANCE_CONTACT, "contact_email": "sy.kim@apacreg.kr", "contact_phone": "+82-2-3456-7890", "contract_start": now - timedelta(days=130), "contract_end": now + timedelta(days=235), "active": True},
            {"id": "AGT-007", "trial_id": LIBTAYO_TRIAL, "country": "Australia", "agent_name": "David Thompson", "organization": "Pacific Regulatory Advisors Pty Ltd", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "d.thompson@pacificreg.com.au", "contact_phone": "+61-2-8765-4321", "contract_start": now - timedelta(days=175), "contract_end": now + timedelta(days=190), "active": True},
            {"id": "AGT-008", "trial_id": LIBTAYO_TRIAL, "country": "Canada", "agent_name": "Catherine Bergeron", "organization": "Canadian CRO Services Inc", "role": AgentRole.LOCAL_REGULATORY_AGENT, "contact_email": "c.bergeron@cancro.ca", "contact_phone": "+1-514-555-0199", "contract_start": now - timedelta(days=90), "contract_end": now + timedelta(days=275), "active": True},
            {"id": "AGT-009", "trial_id": EYLEA_TRIAL, "country": "India", "agent_name": "Rajesh Patel", "organization": "India Pharma Regulatory Consultants", "role": AgentRole.IMPORT_AGENT, "contact_email": "r.patel@inpharmareg.in", "contact_phone": "+91-22-2345-6789", "contract_start": now - timedelta(days=80), "contract_end": now + timedelta(days=285), "active": True},
            {"id": "AGT-010", "trial_id": DUPIXENT_TRIAL, "country": "France", "agent_name": "Jean-Luc Martin", "organization": "PharmaVigilance France", "role": AgentRole.PHARMACOVIGILANCE_CONTACT, "contact_email": "jl.martin@pvfrance.fr", "contact_phone": "+33-1-9876-5432", "contract_start": now - timedelta(days=165), "contract_end": None, "active": False},
        ]

        for a in agents_data:
            self._agents[a["id"]] = LocalAgent(**a)

        # --- 12 Country Activations ---
        activations_data = [
            {"id": "ACT-001", "trial_id": EYLEA_TRIAL, "country": "United States", "country_code": "US", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=150), "actual_activation_date": now - timedelta(days=145), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 15, "sites_activated": 12, "target_enrollment": 300, "current_enrollment": 185},
            {"id": "ACT-002", "trial_id": EYLEA_TRIAL, "country": "United Kingdom", "country_code": "GB", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=120), "actual_activation_date": now - timedelta(days=110), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 8, "sites_activated": 6, "target_enrollment": 120, "current_enrollment": 68},
            {"id": "ACT-003", "trial_id": EYLEA_TRIAL, "country": "Germany", "country_code": "DE", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=110), "actual_activation_date": now - timedelta(days=100), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 10, "sites_activated": 8, "target_enrollment": 150, "current_enrollment": 92},
            {"id": "ACT-004", "trial_id": EYLEA_TRIAL, "country": "Japan", "country_code": "JP", "status": ActivationStatus.IN_PROGRESS, "planned_activation_date": now - timedelta(days=90), "actual_activation_date": None, "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 6, "sites_activated": 3, "target_enrollment": 80, "current_enrollment": 22},
            {"id": "ACT-005", "trial_id": DUPIXENT_TRIAL, "country": "United States", "country_code": "US", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=130), "actual_activation_date": now - timedelta(days=125), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 20, "sites_activated": 18, "target_enrollment": 450, "current_enrollment": 312},
            {"id": "ACT-006", "trial_id": DUPIXENT_TRIAL, "country": "France", "country_code": "FR", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=100), "actual_activation_date": now - timedelta(days=95), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 12, "sites_activated": 10, "target_enrollment": 200, "current_enrollment": 134},
            {"id": "ACT-007", "trial_id": DUPIXENT_TRIAL, "country": "Brazil", "country_code": "BR", "status": ActivationStatus.IN_PROGRESS, "planned_activation_date": now - timedelta(days=60), "actual_activation_date": None, "regulatory_approved": False, "ethics_approved": False, "import_license_obtained": False, "local_agent_assigned": True, "sites_planned": 5, "sites_activated": 0, "target_enrollment": 75, "current_enrollment": 0},
            {"id": "ACT-008", "trial_id": DUPIXENT_TRIAL, "country": "South Korea", "country_code": "KR", "status": ActivationStatus.PLANNED, "planned_activation_date": now + timedelta(days=30), "actual_activation_date": None, "regulatory_approved": False, "ethics_approved": False, "import_license_obtained": False, "local_agent_assigned": True, "sites_planned": 4, "sites_activated": 0, "target_enrollment": 60, "current_enrollment": 0},
            {"id": "ACT-009", "trial_id": LIBTAYO_TRIAL, "country": "United States", "country_code": "US", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=170), "actual_activation_date": now - timedelta(days=165), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 12, "sites_activated": 11, "target_enrollment": 250, "current_enrollment": 198},
            {"id": "ACT-010", "trial_id": LIBTAYO_TRIAL, "country": "Australia", "country_code": "AU", "status": ActivationStatus.ACTIVATED, "planned_activation_date": now - timedelta(days=110), "actual_activation_date": now - timedelta(days=105), "regulatory_approved": True, "ethics_approved": True, "import_license_obtained": True, "local_agent_assigned": True, "sites_planned": 6, "sites_activated": 5, "target_enrollment": 80, "current_enrollment": 56},
            {"id": "ACT-011", "trial_id": LIBTAYO_TRIAL, "country": "Canada", "country_code": "CA", "status": ActivationStatus.PLANNED, "planned_activation_date": now + timedelta(days=60), "actual_activation_date": None, "regulatory_approved": False, "ethics_approved": False, "import_license_obtained": False, "local_agent_assigned": True, "sites_planned": 4, "sites_activated": 0, "target_enrollment": 50, "current_enrollment": 0},
            {"id": "ACT-012", "trial_id": EYLEA_TRIAL, "country": "India", "country_code": "IN", "status": ActivationStatus.SUSPENDED, "planned_activation_date": now - timedelta(days=40), "actual_activation_date": None, "regulatory_approved": False, "ethics_approved": False, "import_license_obtained": False, "local_agent_assigned": True, "sites_planned": 3, "sites_activated": 0, "target_enrollment": 40, "current_enrollment": 0},
        ]

        for act in activations_data:
            self._activations[act["id"]] = CountryActivation(**act)

    # ------------------------------------------------------------------
    # Country Requirements
    # ------------------------------------------------------------------

    def list_requirements(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        approval_status: ApprovalStatus | None = None,
        requirement_type: SubmissionType | None = None,
    ) -> list[CountryRequirement]:
        """List country requirements with optional filters."""
        with self._lock:
            result = list(self._requirements.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if country is not None:
            result = [r for r in result if r.country == country]
        if approval_status is not None:
            result = [r for r in result if r.approval_status == approval_status]
        if requirement_type is not None:
            result = [r for r in result if r.requirement_type == requirement_type]

        return sorted(result, key=lambda r: r.id)

    def get_requirement(self, requirement_id: str) -> CountryRequirement | None:
        """Get a single requirement by ID."""
        with self._lock:
            return self._requirements.get(requirement_id)

    def create_requirement(self, payload: CountryRequirementCreate) -> CountryRequirement:
        """Create a new country requirement."""
        now = datetime.now(timezone.utc)
        requirement_id = f"CREQ-{uuid4().hex[:8].upper()}"
        requirement = CountryRequirement(
            id=requirement_id,
            trial_id=payload.trial_id,
            country=payload.country,
            country_code=payload.country_code,
            requirement_type=payload.requirement_type,
            description=payload.description,
            regulatory_authority=payload.regulatory_authority,
            submission_deadline=payload.submission_deadline,
            responsible_person=payload.responsible_person,
            documents_required=payload.documents_required,
            created_at=now,
        )
        with self._lock:
            self._requirements[requirement_id] = requirement
        logger.info("Created country requirement %s: %s", requirement_id, payload.description)
        return requirement

    def update_requirement(
        self, requirement_id: str, payload: CountryRequirementUpdate
    ) -> CountryRequirement | None:
        """Update an existing country requirement."""
        with self._lock:
            existing = self._requirements.get(requirement_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CountryRequirement(**data)
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
    # Ethics Submissions
    # ------------------------------------------------------------------

    def list_ethics(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        approval_status: ApprovalStatus | None = None,
    ) -> list[EthicsSubmission]:
        """List ethics submissions with optional filters."""
        with self._lock:
            result = list(self._ethics.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if country is not None:
            result = [e for e in result if e.country == country]
        if approval_status is not None:
            result = [e for e in result if e.approval_status == approval_status]

        return sorted(result, key=lambda e: e.id)

    def get_ethics(self, ethics_id: str) -> EthicsSubmission | None:
        """Get a single ethics submission by ID."""
        with self._lock:
            return self._ethics.get(ethics_id)

    def create_ethics(self, payload: EthicsSubmissionCreate) -> EthicsSubmission:
        """Create a new ethics submission."""
        now = datetime.now(timezone.utc)
        ethics_id = f"ETH-{uuid4().hex[:8].upper()}"
        ethics = EthicsSubmission(
            id=ethics_id,
            trial_id=payload.trial_id,
            country=payload.country,
            committee_name=payload.committee_name,
            submission_date=now,
            protocol_version=payload.protocol_version,
            icf_version=payload.icf_version,
            submitted_by=payload.submitted_by,
        )
        with self._lock:
            self._ethics[ethics_id] = ethics
        logger.info("Created ethics submission %s for %s", ethics_id, payload.country)
        return ethics

    def update_ethics(
        self, ethics_id: str, payload: EthicsSubmissionUpdate
    ) -> EthicsSubmission | None:
        """Update an existing ethics submission."""
        with self._lock:
            existing = self._ethics.get(ethics_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EthicsSubmission(**data)
            self._ethics[ethics_id] = updated
        return updated

    def delete_ethics(self, ethics_id: str) -> bool:
        """Delete an ethics submission. Returns True if deleted."""
        with self._lock:
            if ethics_id in self._ethics:
                del self._ethics[ethics_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Import/Export Licenses
    # ------------------------------------------------------------------

    def list_licenses(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        status: ApprovalStatus | None = None,
        license_type: str | None = None,
    ) -> list[ImportExportLicense]:
        """List import/export licenses with optional filters."""
        with self._lock:
            result = list(self._licenses.values())

        if trial_id is not None:
            result = [lic for lic in result if lic.trial_id == trial_id]
        if country is not None:
            result = [lic for lic in result if lic.country == country]
        if status is not None:
            result = [lic for lic in result if lic.status == status]
        if license_type is not None:
            result = [lic for lic in result if lic.license_type == license_type]

        return sorted(result, key=lambda lic: lic.id)

    def get_license(self, license_id: str) -> ImportExportLicense | None:
        """Get a single license by ID."""
        with self._lock:
            return self._licenses.get(license_id)

    def create_license(self, payload: ImportExportLicenseCreate) -> ImportExportLicense:
        """Create a new import/export license."""
        now = datetime.now(timezone.utc)
        license_id = f"LIC-{uuid4().hex[:8].upper()}"
        license_obj = ImportExportLicense(
            id=license_id,
            trial_id=payload.trial_id,
            country=payload.country,
            license_type=payload.license_type,
            product_name=payload.product_name,
            quantity_authorized=payload.quantity_authorized,
            responsible_person=payload.responsible_person,
            application_date=now,
        )
        with self._lock:
            self._licenses[license_id] = license_obj
        logger.info("Created license %s for %s", license_id, payload.country)
        return license_obj

    def update_license(
        self, license_id: str, payload: ImportExportLicenseUpdate
    ) -> ImportExportLicense | None:
        """Update an existing import/export license."""
        with self._lock:
            existing = self._licenses.get(license_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ImportExportLicense(**data)
            self._licenses[license_id] = updated
        return updated

    def delete_license(self, license_id: str) -> bool:
        """Delete a license. Returns True if deleted."""
        with self._lock:
            if license_id in self._licenses:
                del self._licenses[license_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Local Agents
    # ------------------------------------------------------------------

    def list_agents(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        role: AgentRole | None = None,
        active: bool | None = None,
    ) -> list[LocalAgent]:
        """List local agents with optional filters."""
        with self._lock:
            result = list(self._agents.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if country is not None:
            result = [a for a in result if a.country == country]
        if role is not None:
            result = [a for a in result if a.role == role]
        if active is not None:
            result = [a for a in result if a.active == active]

        return sorted(result, key=lambda a: a.id)

    def get_agent(self, agent_id: str) -> LocalAgent | None:
        """Get a single agent by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def create_agent(self, payload: LocalAgentCreate) -> LocalAgent:
        """Create a new local agent."""
        agent_id = f"AGT-{uuid4().hex[:8].upper()}"
        agent = LocalAgent(
            id=agent_id,
            trial_id=payload.trial_id,
            country=payload.country,
            agent_name=payload.agent_name,
            organization=payload.organization,
            role=payload.role,
            contact_email=payload.contact_email,
            contact_phone=payload.contact_phone,
            contract_start=payload.contract_start,
            contract_end=payload.contract_end,
        )
        with self._lock:
            self._agents[agent_id] = agent
        logger.info("Created local agent %s: %s", agent_id, payload.agent_name)
        return agent

    def update_agent(
        self, agent_id: str, payload: LocalAgentUpdate
    ) -> LocalAgent | None:
        """Update an existing local agent."""
        with self._lock:
            existing = self._agents.get(agent_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LocalAgent(**data)
            self._agents[agent_id] = updated
        return updated

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent. Returns True if deleted."""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Country Activations
    # ------------------------------------------------------------------

    def list_activations(
        self,
        *,
        trial_id: str | None = None,
        country: str | None = None,
        status: ActivationStatus | None = None,
    ) -> list[CountryActivation]:
        """List country activations with optional filters."""
        with self._lock:
            result = list(self._activations.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if country is not None:
            result = [a for a in result if a.country == country]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.id)

    def get_activation(self, activation_id: str) -> CountryActivation | None:
        """Get a single activation by ID."""
        with self._lock:
            return self._activations.get(activation_id)

    def create_activation(self, payload: CountryActivationCreate) -> CountryActivation:
        """Create a new country activation."""
        activation_id = f"ACT-{uuid4().hex[:8].upper()}"
        activation = CountryActivation(
            id=activation_id,
            trial_id=payload.trial_id,
            country=payload.country,
            country_code=payload.country_code,
            planned_activation_date=payload.planned_activation_date,
            sites_planned=payload.sites_planned,
            target_enrollment=payload.target_enrollment,
        )
        with self._lock:
            self._activations[activation_id] = activation
        logger.info("Created country activation %s: %s", activation_id, payload.country)
        return activation

    def update_activation(
        self, activation_id: str, payload: CountryActivationUpdate
    ) -> CountryActivation | None:
        """Update an existing country activation."""
        with self._lock:
            existing = self._activations.get(activation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CountryActivation(**data)
            self._activations[activation_id] = updated
        return updated

    def delete_activation(self, activation_id: str) -> bool:
        """Delete an activation. Returns True if deleted."""
        with self._lock:
            if activation_id in self._activations:
                del self._activations[activation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> CountryRegulatoryMetrics:
        """Compute aggregated country regulatory metrics."""
        with self._lock:
            requirements = list(self._requirements.values())
            ethics = list(self._ethics.values())
            licenses = list(self._licenses.values())
            agents = list(self._agents.values())
            activations = list(self._activations.values())

        if trial_id is not None:
            requirements = [r for r in requirements if r.trial_id == trial_id]
            ethics = [e for e in ethics if e.trial_id == trial_id]
            licenses = [lic for lic in licenses if lic.trial_id == trial_id]
            agents = [a for a in agents if a.trial_id == trial_id]
            activations = [act for act in activations if act.trial_id == trial_id]

        # Requirements by status
        requirements_by_status: dict[str, int] = {}
        for r in requirements:
            key = r.approval_status.value
            requirements_by_status[key] = requirements_by_status.get(key, 0) + 1

        # Requirements by type
        requirements_by_type: dict[str, int] = {}
        for r in requirements:
            key = r.requirement_type.value
            requirements_by_type[key] = requirements_by_type.get(key, 0) + 1

        # Ethics by status
        ethics_by_status: dict[str, int] = {}
        for e in ethics:
            key = e.approval_status.value
            ethics_by_status[key] = ethics_by_status.get(key, 0) + 1

        # Licenses by status
        licenses_by_status: dict[str, int] = {}
        for lic in licenses:
            key = lic.status.value
            licenses_by_status[key] = licenses_by_status.get(key, 0) + 1

        # Agents
        active_agents = sum(1 for a in agents if a.active)

        # Activations by status
        countries_by_status: dict[str, int] = {}
        for act in activations:
            key = act.status.value
            countries_by_status[key] = countries_by_status.get(key, 0) + 1

        total_countries = len(activations)
        countries_activated = sum(
            1 for act in activations if act.status == ActivationStatus.ACTIVATED
        )
        overall_activation_pct = (
            round(countries_activated / total_countries * 100.0, 1)
            if total_countries > 0
            else 0.0
        )

        return CountryRegulatoryMetrics(
            total_requirements=len(requirements),
            requirements_by_status=requirements_by_status,
            requirements_by_type=requirements_by_type,
            total_ethics_submissions=len(ethics),
            ethics_by_status=ethics_by_status,
            total_licenses=len(licenses),
            licenses_by_status=licenses_by_status,
            total_agents=len(agents),
            active_agents=active_agents,
            total_countries=total_countries,
            countries_activated=countries_activated,
            countries_by_status=countries_by_status,
            overall_activation_pct=overall_activation_pct,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CountryRegulatoryService | None = None
_instance_lock = threading.Lock()


def get_country_regulatory_service() -> CountryRegulatoryService:
    """Return the singleton CountryRegulatoryService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CountryRegulatoryService()
    return _instance


def reset_country_regulatory_service() -> CountryRegulatoryService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CountryRegulatoryService()
    return _instance
