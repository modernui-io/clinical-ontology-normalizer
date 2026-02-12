"""Regulatory Intelligence Hub Service (REG-INTEL).

Manages regulatory intelligence operations: landscape monitoring,
guideline tracking, authority communication records, impact
assessments, and compliance alert management with intelligence metrics.

Usage:
    from app.services.regulatory_intelligence_hub_service import (
        get_regulatory_intelligence_hub_service,
    )

    svc = get_regulatory_intelligence_hub_service()
    monitors = svc.list_landscape_monitors()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.regulatory_intelligence_hub import (
    AlertSeverity,
    AuthorityCommunication,
    AuthorityCommunicationCreate,
    AuthorityCommunicationUpdate,
    CommunicationType,
    ComplianceAlert,
    ComplianceAlertCreate,
    ComplianceAlertUpdate,
    GuidelineTracker,
    GuidelineTrackerCreate,
    GuidelineTrackerUpdate,
    ImpactAssessment,
    ImpactAssessmentCreate,
    ImpactAssessmentUpdate,
    ImpactLevel,
    IntelligenceType,
    LandscapeMonitor,
    LandscapeMonitorCreate,
    LandscapeMonitorUpdate,
    RegionScope,
    RegulatoryIntelligenceMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class RegulatoryIntelligenceHubService:
    """In-memory Regulatory Intelligence Hub engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._landscape_monitors: dict[str, LandscapeMonitor] = {}
        self._guideline_trackers: dict[str, GuidelineTracker] = {}
        self._authority_communications: dict[str, AuthorityCommunication] = {}
        self._impact_assessments: dict[str, ImpactAssessment] = {}
        self._compliance_alerts: dict[str, ComplianceAlert] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic regulatory intelligence data."""
        now = datetime.now(timezone.utc)

        # --- 12 Landscape Monitors ---
        monitor_data = [
            {
                "id": "LM-001",
                "trial_id": EYLEA_TRIAL,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "region": RegionScope.US_FDA,
                "title": "FDA Draft Guidance on Anti-VEGF Biosimilar Development",
                "description": "New draft guidance outlining clinical trial requirements for anti-VEGF biosimilar products including aflibercept biosimilars.",
                "source_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
                "publication_date": now - timedelta(days=45),
                "effective_date": now + timedelta(days=90),
                "impact_level": ImpactLevel.HIGH,
                "therapeutic_area": "Ophthalmology",
                "drug_class_affected": "Anti-VEGF",
                "action_required": True,
                "action_deadline": now + timedelta(days=60),
                "analyzed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=40),
                "monitored_by": "Dr. Sarah Chen",
                "notes": "May impact EYLEA trial endpoints and comparator design.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "LM-002",
                "trial_id": EYLEA_TRIAL,
                "intelligence_type": IntelligenceType.REGULATION_CHANGE,
                "region": RegionScope.EU_EMA,
                "title": "EMA Revision of Ophthalmology Clinical Trial Endpoints",
                "description": "Revised guidance on acceptable primary endpoints for intravitreal anti-VEGF trials including BCVA and central subfield thickness.",
                "source_url": "https://www.ema.europa.eu/en/human-regulatory-overview",
                "publication_date": now - timedelta(days=90),
                "effective_date": now - timedelta(days=30),
                "impact_level": ImpactLevel.MODERATE,
                "therapeutic_area": "Ophthalmology",
                "drug_class_affected": "Anti-VEGF",
                "action_required": True,
                "action_deadline": now + timedelta(days=30),
                "analyzed": True,
                "analyzed_by": "Dr. James Wright",
                "analysis_date": now - timedelta(days=85),
                "monitored_by": "Dr. James Wright",
                "notes": "Protocol amendment may be needed for EU sites.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "LM-003",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "region": RegionScope.US_FDA,
                "title": "FDA Guidance on Biomarker-Driven Atopic Dermatitis Trials",
                "description": "Updated guidance recommending incorporation of Type 2 inflammatory biomarkers as stratification factors in atopic dermatitis trials.",
                "source_url": "https://www.fda.gov/drugs/biomarker-qualification-program",
                "publication_date": now - timedelta(days=60),
                "effective_date": now + timedelta(days=120),
                "impact_level": ImpactLevel.HIGH,
                "therapeutic_area": "Dermatology",
                "drug_class_affected": "IL-4/IL-13 Inhibitors",
                "action_required": True,
                "action_deadline": now + timedelta(days=90),
                "analyzed": True,
                "analyzed_by": "Dr. Maria Lopez",
                "analysis_date": now - timedelta(days=55),
                "monitored_by": "Dr. Maria Lopez",
                "notes": "Biomarker stratification aligns with DUPIXENT mechanism. Protocol update recommended.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "LM-004",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_type": IntelligenceType.POLICY_SHIFT,
                "region": RegionScope.GLOBAL,
                "title": "ICH E9(R1) Estimand Framework Implementation Timeline",
                "description": "Updated ICH implementation timeline requiring estimand framework adoption for all new submissions by Q4 2026.",
                "source_url": "https://www.ich.org/page/efficacy-guidelines",
                "publication_date": now - timedelta(days=120),
                "effective_date": now + timedelta(days=180),
                "impact_level": ImpactLevel.MODERATE,
                "therapeutic_area": None,
                "drug_class_affected": None,
                "action_required": True,
                "action_deadline": now + timedelta(days=150),
                "analyzed": True,
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=115),
                "monitored_by": "Dr. Robert Kim",
                "notes": "SAP revision needed to incorporate estimand framework explicitly.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "LM-005",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_type": IntelligenceType.ENFORCEMENT_ACTION,
                "region": RegionScope.US_FDA,
                "title": "FDA Warning Letter to CRO on Checkpoint Inhibitor Data Integrity",
                "description": "FDA issued warning letter to a major CRO regarding data integrity findings in checkpoint inhibitor oncology trials.",
                "source_url": "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations",
                "publication_date": now - timedelta(days=30),
                "effective_date": None,
                "impact_level": ImpactLevel.CRITICAL,
                "therapeutic_area": "Oncology",
                "drug_class_affected": "PD-1/PD-L1 Inhibitors",
                "action_required": True,
                "action_deadline": now + timedelta(days=14),
                "analyzed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=28),
                "monitored_by": "Dr. Angela Park",
                "notes": "CRO involved is not our primary CRO but handles 3 LIBTAYO sites. Urgent audit needed.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "LM-006",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_type": IntelligenceType.GUIDANCE_UPDATE,
                "region": RegionScope.US_FDA,
                "title": "FDA Project Orbis Expansion to Include Cutaneous SCC",
                "description": "FDA expands Project Orbis international concurrent review program to include cutaneous squamous cell carcinoma indications.",
                "source_url": "https://www.fda.gov/about-fda/oncology-center-excellence/project-orbis",
                "publication_date": now - timedelta(days=75),
                "effective_date": now - timedelta(days=15),
                "impact_level": ImpactLevel.MODERATE,
                "therapeutic_area": "Oncology",
                "drug_class_affected": "PD-1/PD-L1 Inhibitors",
                "action_required": False,
                "action_deadline": None,
                "analyzed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=70),
                "monitored_by": "Dr. Angela Park",
                "notes": "Potential for expedited multi-regional approval. Beneficial for LIBTAYO program.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "LM-007",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_type": IntelligenceType.ADVISORY_NOTICE,
                "region": RegionScope.UK_MHRA,
                "title": "MHRA Advisory on Immune-Related Adverse Event Monitoring",
                "description": "MHRA advisory recommending enhanced monitoring protocols for immune-related adverse events in PD-1/PD-L1 inhibitor trials.",
                "source_url": "https://www.gov.uk/government/organisations/medicines-and-healthcare-products-regulatory-agency",
                "publication_date": now - timedelta(days=20),
                "effective_date": now,
                "impact_level": ImpactLevel.HIGH,
                "therapeutic_area": "Oncology",
                "drug_class_affected": "PD-1/PD-L1 Inhibitors",
                "action_required": True,
                "action_deadline": now + timedelta(days=45),
                "analyzed": False,
                "analyzed_by": None,
                "analysis_date": None,
                "monitored_by": "Dr. Angela Park",
                "notes": "Pending analysis. UK sites need updated monitoring SOP.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "LM-008",
                "trial_id": EYLEA_TRIAL,
                "intelligence_type": IntelligenceType.INDUSTRY_TREND,
                "region": RegionScope.GLOBAL,
                "title": "Competitor Aflibercept 8mg Higher-Dose Filing Accepted",
                "description": "Competitor higher-dose aflibercept formulation accepted for review by FDA and EMA simultaneously.",
                "source_url": None,
                "publication_date": now - timedelta(days=15),
                "effective_date": None,
                "impact_level": ImpactLevel.HIGH,
                "therapeutic_area": "Ophthalmology",
                "drug_class_affected": "Anti-VEGF",
                "action_required": False,
                "action_deadline": None,
                "analyzed": True,
                "analyzed_by": "Dr. Sarah Chen",
                "analysis_date": now - timedelta(days=12),
                "monitored_by": "Dr. Sarah Chen",
                "notes": "Competitive intelligence. May affect commercial strategy but not current trial design.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "LM-009",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_type": IntelligenceType.REGULATION_CHANGE,
                "region": RegionScope.JAPAN_PMDA,
                "title": "PMDA Revised Requirements for Pediatric Atopic Dermatitis Trials",
                "description": "PMDA issued revised requirements for pediatric populations in atopic dermatitis trials including age stratification and endpoint selection.",
                "source_url": "https://www.pmda.go.jp/english/",
                "publication_date": now - timedelta(days=50),
                "effective_date": now + timedelta(days=60),
                "impact_level": ImpactLevel.MODERATE,
                "therapeutic_area": "Dermatology",
                "drug_class_affected": "IL-4/IL-13 Inhibitors",
                "action_required": True,
                "action_deadline": now + timedelta(days=45),
                "analyzed": False,
                "analyzed_by": None,
                "analysis_date": None,
                "monitored_by": "Dr. Maria Lopez",
                "notes": "Awaiting translation of full guidance document.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "LM-010",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_type": IntelligenceType.POLICY_SHIFT,
                "region": RegionScope.CHINA_NMPA,
                "title": "NMPA New Policy on Accelerated Approval for Oncology Drugs",
                "description": "NMPA announces expedited review pathway for PD-1/PD-L1 inhibitors in rare tumor types with unmet medical need.",
                "source_url": "https://www.nmpa.gov.cn/",
                "publication_date": now - timedelta(days=35),
                "effective_date": now + timedelta(days=30),
                "impact_level": ImpactLevel.LOW,
                "therapeutic_area": "Oncology",
                "drug_class_affected": "PD-1/PD-L1 Inhibitors",
                "action_required": False,
                "action_deadline": None,
                "analyzed": True,
                "analyzed_by": "Dr. Angela Park",
                "analysis_date": now - timedelta(days=30),
                "monitored_by": "Dr. Angela Park",
                "notes": "Potentially relevant for future LIBTAYO indications in China.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "LM-011",
                "trial_id": EYLEA_TRIAL,
                "intelligence_type": IntelligenceType.ADVISORY_NOTICE,
                "region": RegionScope.EU_EMA,
                "title": "EMA PRAC Safety Signal Review on Intravitreal Injections",
                "description": "EMA Pharmacovigilance Risk Assessment Committee initiated safety signal review for thromboembolic events associated with repeated intravitreal anti-VEGF injections.",
                "source_url": "https://www.ema.europa.eu/en/committees/prac",
                "publication_date": now - timedelta(days=10),
                "effective_date": None,
                "impact_level": ImpactLevel.HIGH,
                "therapeutic_area": "Ophthalmology",
                "drug_class_affected": "Anti-VEGF",
                "action_required": True,
                "action_deadline": now + timedelta(days=30),
                "analyzed": False,
                "analyzed_by": None,
                "analysis_date": None,
                "monitored_by": "Dr. James Wright",
                "notes": "Urgent: need safety data review from EYLEA trial for PRAC submission.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "LM-012",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_type": IntelligenceType.ENFORCEMENT_ACTION,
                "region": RegionScope.US_FDA,
                "title": "FDA Complete Response Letter to Competitor IL-13 Inhibitor",
                "description": "FDA issues complete response letter to competitor IL-13 inhibitor for atopic dermatitis due to manufacturing deficiencies.",
                "source_url": None,
                "publication_date": now - timedelta(days=5),
                "effective_date": None,
                "impact_level": ImpactLevel.LOW,
                "therapeutic_area": "Dermatology",
                "drug_class_affected": "IL-4/IL-13 Inhibitors",
                "action_required": False,
                "action_deadline": None,
                "analyzed": True,
                "analyzed_by": "Dr. Robert Kim",
                "analysis_date": now - timedelta(days=3),
                "monitored_by": "Dr. Maria Lopez",
                "notes": "Competitive intelligence. No direct impact on DUPIXENT program.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for m in monitor_data:
            self._landscape_monitors[m["id"]] = LandscapeMonitor(**m)

        # --- 12 Guideline Trackers ---
        guideline_data = [
            {
                "id": "GT-001",
                "trial_id": EYLEA_TRIAL,
                "guideline_name": "ICH E6(R3) Good Clinical Practice",
                "issuing_authority": "ICH",
                "region": RegionScope.GLOBAL,
                "version": "R3 Step 4",
                "effective_date": now - timedelta(days=180),
                "supersedes_version": "R2",
                "key_changes": [
                    "Risk-based quality management",
                    "Enhanced data governance",
                    "Decentralized trial elements",
                    "Electronic records and signatures",
                ],
                "impact_on_protocol": True,
                "impact_on_operations": True,
                "compliance_gap_identified": True,
                "remediation_plan": "Update TMF structure, retrain site staff on risk-based monitoring, revise informed consent process.",
                "remediation_deadline": now + timedelta(days=60),
                "tracked_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. James Wright",
                "notes": "Major guideline revision. Gap assessment completed.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "GT-002",
                "trial_id": EYLEA_TRIAL,
                "guideline_name": "AAO Preferred Practice Pattern: Age-Related Macular Degeneration",
                "issuing_authority": "American Academy of Ophthalmology",
                "region": RegionScope.US_FDA,
                "version": "2025",
                "effective_date": now - timedelta(days=90),
                "supersedes_version": "2019",
                "key_changes": [
                    "Updated OCT imaging criteria",
                    "New treat-and-extend protocols",
                    "Fluid management algorithm update",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": True,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Sarah Chen",
                "reviewed_by": "Dr. Sarah Chen",
                "notes": "Trial endpoints align with updated PPP. No protocol changes needed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "GT-003",
                "trial_id": DUPIXENT_TRIAL,
                "guideline_name": "AAD Guidelines of Care: Atopic Dermatitis Management",
                "issuing_authority": "American Academy of Dermatology",
                "region": RegionScope.US_FDA,
                "version": "2024 Update",
                "effective_date": now - timedelta(days=150),
                "supersedes_version": "2022",
                "key_changes": [
                    "Dupilumab positioned as first-line biologic",
                    "EASI-75 validated as primary endpoint",
                    "Biomarker-driven treatment selection recommended",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": False,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Maria Lopez",
                "notes": "Trial design consistent with updated guidelines. Favorable positioning.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "GT-004",
                "trial_id": DUPIXENT_TRIAL,
                "guideline_name": "EMA Guideline on Clinical Investigation of Medicinal Products for Treatment of Atopic Dermatitis",
                "issuing_authority": "EMA CHMP",
                "region": RegionScope.EU_EMA,
                "version": "Rev 2",
                "effective_date": now - timedelta(days=60),
                "supersedes_version": "Rev 1",
                "key_changes": [
                    "PRO co-primary endpoint requirement",
                    "Long-term safety follow-up extension",
                    "Rescue therapy handling clarification",
                ],
                "impact_on_protocol": True,
                "impact_on_operations": False,
                "compliance_gap_identified": True,
                "remediation_plan": "Add DLQI as co-primary PRO endpoint for EU submission. Protocol amendment in progress.",
                "remediation_deadline": now + timedelta(days=45),
                "tracked_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "Protocol amendment v3.1 being prepared to address PRO requirement.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "GT-005",
                "trial_id": LIBTAYO_TRIAL,
                "guideline_name": "NCCN Clinical Practice Guidelines: Cutaneous SCC",
                "issuing_authority": "National Comprehensive Cancer Network",
                "region": RegionScope.US_FDA,
                "version": "Version 2.2025",
                "effective_date": now - timedelta(days=45),
                "supersedes_version": "Version 1.2025",
                "key_changes": [
                    "Cemiplimab added as preferred first-line for advanced CSCC",
                    "Updated staging criteria",
                    "New combination therapy recommendations",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": False,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Angela Park",
                "reviewed_by": "Dr. Angela Park",
                "notes": "NCCN update is favorable for LIBTAYO positioning. No trial changes needed.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "GT-006",
                "trial_id": LIBTAYO_TRIAL,
                "guideline_name": "ESMO Clinical Practice Guidelines: Cutaneous SCC",
                "issuing_authority": "European Society for Medical Oncology",
                "region": RegionScope.EU_EMA,
                "version": "2025",
                "effective_date": now - timedelta(days=30),
                "supersedes_version": "2023",
                "key_changes": [
                    "Anti-PD-1 recommended as standard of care",
                    "Updated response assessment criteria",
                    "Biomarker testing recommendations",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": True,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Need to update investigator training materials to reflect ESMO updates.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "GT-007",
                "trial_id": EYLEA_TRIAL,
                "guideline_name": "FDA Guidance on Retinal Endpoint Assessment",
                "issuing_authority": "FDA CDER",
                "region": RegionScope.US_FDA,
                "version": "Final",
                "effective_date": now - timedelta(days=120),
                "supersedes_version": "Draft",
                "key_changes": [
                    "SD-OCT acceptable as primary endpoint measure",
                    "Central reading center requirements updated",
                    "Visual function testing standardization",
                ],
                "impact_on_protocol": True,
                "impact_on_operations": True,
                "compliance_gap_identified": True,
                "remediation_plan": "Update central reading center contract and certification. Align OCT protocols.",
                "remediation_deadline": now + timedelta(days=30),
                "tracked_by": "Dr. James Wright",
                "reviewed_by": "Dr. Sarah Chen",
                "notes": "Reading center update in progress. Expected completion in 3 weeks.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "GT-008",
                "trial_id": DUPIXENT_TRIAL,
                "guideline_name": "ICH E8(R1) General Considerations for Clinical Studies",
                "issuing_authority": "ICH",
                "region": RegionScope.GLOBAL,
                "version": "R1 Final",
                "effective_date": now - timedelta(days=200),
                "supersedes_version": "E8",
                "key_changes": [
                    "Quality by design approach",
                    "Stakeholder engagement requirements",
                    "Fit-for-purpose study design",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": True,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Robert Kim",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "Already implemented QbD approach. No additional changes needed.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "GT-009",
                "trial_id": LIBTAYO_TRIAL,
                "guideline_name": "FDA Guidance on Tumor-Agnostic Drug Development",
                "issuing_authority": "FDA CDER",
                "region": RegionScope.US_FDA,
                "version": "Draft",
                "effective_date": now + timedelta(days=90),
                "supersedes_version": None,
                "key_changes": [
                    "Biomarker-selected trial design guidance",
                    "Basket trial statistical considerations",
                    "Accelerated approval pathway criteria",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": False,
                "compliance_gap_identified": False,
                "remediation_plan": None,
                "remediation_deadline": None,
                "tracked_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Draft guidance. Monitoring for final version. May impact future LIBTAYO indications.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "GT-010",
                "trial_id": EYLEA_TRIAL,
                "guideline_name": "EMA Guideline on Intravitreal Formulations Quality Requirements",
                "issuing_authority": "EMA CHMP",
                "region": RegionScope.EU_EMA,
                "version": "Rev 1",
                "effective_date": now - timedelta(days=40),
                "supersedes_version": None,
                "key_changes": [
                    "Container closure integrity requirements",
                    "Endotoxin testing frequency",
                    "Stability testing in use conditions",
                ],
                "impact_on_protocol": False,
                "impact_on_operations": True,
                "compliance_gap_identified": True,
                "remediation_plan": "Update stability testing protocol and CMC documentation for EU filing.",
                "remediation_deadline": now + timedelta(days=75),
                "tracked_by": "Dr. James Wright",
                "reviewed_by": None,
                "notes": "CMC team leading remediation. Clinical trial operations minimally affected.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "GT-011",
                "trial_id": DUPIXENT_TRIAL,
                "guideline_name": "PMDA Guidance on Biologics for Inflammatory Diseases",
                "issuing_authority": "PMDA",
                "region": RegionScope.JAPAN_PMDA,
                "version": "2025",
                "effective_date": now - timedelta(days=80),
                "supersedes_version": "2021",
                "key_changes": [
                    "Immunogenicity testing requirements update",
                    "Japanese-specific subgroup analysis requirements",
                    "Long-term safety data expectations",
                ],
                "impact_on_protocol": True,
                "impact_on_operations": True,
                "compliance_gap_identified": True,
                "remediation_plan": "Add Japanese subgroup analysis to SAP. Extend immunogenicity sampling schedule for Japanese sites.",
                "remediation_deadline": now + timedelta(days=90),
                "tracked_by": "Dr. Maria Lopez",
                "reviewed_by": "Dr. Robert Kim",
                "notes": "SAP amendment being prepared. Japanese CRA team informed.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "GT-012",
                "trial_id": LIBTAYO_TRIAL,
                "guideline_name": "NMPA Technical Guidelines for Immuno-Oncology Clinical Trials",
                "issuing_authority": "NMPA",
                "region": RegionScope.CHINA_NMPA,
                "version": "2025 Edition",
                "effective_date": now - timedelta(days=15),
                "supersedes_version": "2022 Edition",
                "key_changes": [
                    "PD-L1 testing standardization requirements",
                    "Chinese patient population enrollment mandates",
                    "Companion diagnostic co-development expectations",
                ],
                "impact_on_protocol": True,
                "impact_on_operations": True,
                "compliance_gap_identified": True,
                "remediation_plan": "Coordinate with China CRO on PD-L1 testing lab qualification and companion diagnostic strategy.",
                "remediation_deadline": now + timedelta(days=120),
                "tracked_by": "Dr. Angela Park",
                "reviewed_by": None,
                "notes": "Significant impact on China sites. Cross-functional team meeting scheduled.",
                "created_at": now - timedelta(days=15),
            },
        ]

        for g in guideline_data:
            self._guideline_trackers[g["id"]] = GuidelineTracker(**g)

        # --- 12 Authority Communications ---
        communication_data = [
            {
                "id": "AC-001",
                "trial_id": EYLEA_TRIAL,
                "communication_type": CommunicationType.TYPE_B_MEETING,
                "authority": "FDA CDER Division of Transplant and Ophthalmology Products",
                "region": RegionScope.US_FDA,
                "subject": "End-of-Phase 2 Meeting for EYLEA HD Formulation",
                "communication_date": now - timedelta(days=150),
                "response_date": now - timedelta(days=120),
                "reference_number": "FDA-2025-EOP2-001",
                "questions_submitted": 8,
                "questions_answered": 8,
                "outcome_favorable": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Sarah Chen",
                "attendees": ["Dr. Sarah Chen", "Dr. James Wright", "VP Regulatory Affairs", "FDA Division Director"],
                "notes": "FDA agreed with proposed Phase 3 design including non-inferiority margin.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "AC-002",
                "trial_id": EYLEA_TRIAL,
                "communication_type": CommunicationType.SCIENTIFIC_ADVICE,
                "authority": "EMA CHMP Scientific Advice Working Party",
                "region": RegionScope.EU_EMA,
                "subject": "Scientific Advice on EYLEA Phase 3 Design for EU Submission",
                "communication_date": now - timedelta(days=130),
                "response_date": now - timedelta(days=95),
                "reference_number": "EMA/SAWP/2025/001",
                "questions_submitted": 12,
                "questions_answered": 12,
                "outcome_favorable": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=30),
                "meeting_minutes_filed": True,
                "managed_by": "Dr. James Wright",
                "attendees": ["Dr. James Wright", "Dr. Sarah Chen", "EU Regulatory Lead", "EMA SAWP Members"],
                "notes": "EMA recommended adding PRO co-primary endpoint. Follow-up to confirm endpoint alignment.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "AC-003",
                "trial_id": DUPIXENT_TRIAL,
                "communication_type": CommunicationType.TYPE_B_MEETING,
                "authority": "FDA CDER Division of Dermatology and Dentistry",
                "region": RegionScope.US_FDA,
                "subject": "Pre-sNDA Meeting for DUPIXENT New Indication",
                "communication_date": now - timedelta(days=100),
                "response_date": now - timedelta(days=70),
                "reference_number": "FDA-2025-PSNDA-002",
                "questions_submitted": 6,
                "questions_answered": 5,
                "outcome_favorable": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=15),
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Maria Lopez",
                "attendees": ["Dr. Maria Lopez", "Dr. Robert Kim", "CMC Lead", "FDA Reviewer"],
                "notes": "FDA generally supportive. One question on pediatric extrapolation deferred to Type A meeting.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "AC-004",
                "trial_id": DUPIXENT_TRIAL,
                "communication_type": CommunicationType.TYPE_A_MEETING,
                "authority": "FDA CDER Division of Dermatology and Dentistry",
                "region": RegionScope.US_FDA,
                "subject": "Type A Meeting: Pediatric Extrapolation Strategy for DUPIXENT",
                "communication_date": now - timedelta(days=40),
                "response_date": now - timedelta(days=25),
                "reference_number": "FDA-2025-TA-003",
                "questions_submitted": 3,
                "questions_answered": 3,
                "outcome_favorable": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Maria Lopez",
                "attendees": ["Dr. Maria Lopez", "Pediatric Specialist", "FDA Pediatric Team"],
                "notes": "FDA accepted pediatric extrapolation approach with PK bridging study.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "AC-005",
                "trial_id": LIBTAYO_TRIAL,
                "communication_type": CommunicationType.TYPE_B_MEETING,
                "authority": "FDA CDER Division of Oncology Products",
                "region": RegionScope.US_FDA,
                "subject": "End-of-Phase 2 Meeting for LIBTAYO Combination Therapy",
                "communication_date": now - timedelta(days=80),
                "response_date": now - timedelta(days=50),
                "reference_number": "FDA-2025-EOP2-004",
                "questions_submitted": 10,
                "questions_answered": 9,
                "outcome_favorable": True,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=45),
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Angela Park",
                "attendees": ["Dr. Angela Park", "VP Oncology", "Biostatistics Lead", "FDA Division Director"],
                "notes": "FDA agreed with Phase 3 design. One outstanding question on companion diagnostic strategy.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "AC-006",
                "trial_id": LIBTAYO_TRIAL,
                "communication_type": CommunicationType.WRITTEN_INQUIRY,
                "authority": "EMA CHMP",
                "region": RegionScope.EU_EMA,
                "subject": "Written Inquiry on LIBTAYO CSCC Data Package for EU MAA",
                "communication_date": now - timedelta(days=60),
                "response_date": None,
                "reference_number": "EMA/WI/2025/005",
                "questions_submitted": 5,
                "questions_answered": 0,
                "outcome_favorable": None,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=10),
                "meeting_minutes_filed": False,
                "managed_by": "Dr. Angela Park",
                "attendees": [],
                "notes": "Response pending. EMA requested additional long-term survival data.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "AC-007",
                "trial_id": DUPIXENT_TRIAL,
                "communication_type": CommunicationType.SCIENTIFIC_ADVICE,
                "authority": "PMDA",
                "region": RegionScope.JAPAN_PMDA,
                "subject": "PMDA Consultation on DUPIXENT Japanese Bridging Strategy",
                "communication_date": now - timedelta(days=90),
                "response_date": now - timedelta(days=60),
                "reference_number": "PMDA-2025-SA-006",
                "questions_submitted": 7,
                "questions_answered": 7,
                "outcome_favorable": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Robert Kim",
                "attendees": ["Dr. Robert Kim", "Japan Medical Director", "PMDA Reviewers"],
                "notes": "PMDA accepted bridging approach with reduced Japanese sample size requirement.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "AC-008",
                "trial_id": EYLEA_TRIAL,
                "communication_type": CommunicationType.PRE_SUBMISSION,
                "authority": "MHRA",
                "region": RegionScope.UK_MHRA,
                "subject": "Pre-Submission Meeting for EYLEA UK Marketing Authorization",
                "communication_date": now - timedelta(days=20),
                "response_date": None,
                "reference_number": "MHRA-2025-PS-007",
                "questions_submitted": 4,
                "questions_answered": 0,
                "outcome_favorable": None,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=20),
                "meeting_minutes_filed": False,
                "managed_by": "Dr. James Wright",
                "attendees": ["Dr. James Wright", "UK Regulatory Lead"],
                "notes": "Awaiting MHRA response. Meeting date being scheduled.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "AC-009",
                "trial_id": LIBTAYO_TRIAL,
                "communication_type": CommunicationType.TYPE_C_MEETING,
                "authority": "FDA CDER Division of Oncology Products",
                "region": RegionScope.US_FDA,
                "subject": "Type C Meeting: LIBTAYO Accelerated Approval Data Requirements",
                "communication_date": now - timedelta(days=15),
                "response_date": None,
                "reference_number": "FDA-2025-TC-008",
                "questions_submitted": 4,
                "questions_answered": 0,
                "outcome_favorable": None,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=60),
                "meeting_minutes_filed": False,
                "managed_by": "Dr. Angela Park",
                "attendees": ["Dr. Angela Park", "Biostatistics Lead"],
                "notes": "Requesting FDA feedback on accelerated approval pathway for new tumor type.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "AC-010",
                "trial_id": DUPIXENT_TRIAL,
                "communication_type": CommunicationType.TYPE_C_MEETING,
                "authority": "FDA CDER",
                "region": RegionScope.US_FDA,
                "subject": "Type C Meeting: Real-World Evidence Integration for DUPIXENT Label Expansion",
                "communication_date": now - timedelta(days=8),
                "response_date": None,
                "reference_number": "FDA-2025-TC-009",
                "questions_submitted": 5,
                "questions_answered": 0,
                "outcome_favorable": None,
                "follow_up_required": True,
                "follow_up_date": now + timedelta(days=75),
                "meeting_minutes_filed": False,
                "managed_by": "Dr. Maria Lopez",
                "attendees": ["Dr. Maria Lopez", "RWE Lead"],
                "notes": "Exploring FDA receptivity to RWE for label expansion in additional atopic conditions.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "AC-011",
                "trial_id": EYLEA_TRIAL,
                "communication_type": CommunicationType.WRITTEN_INQUIRY,
                "authority": "FDA CDER",
                "region": RegionScope.US_FDA,
                "subject": "Written Inquiry on Post-Marketing Safety Reporting for EYLEA",
                "communication_date": now - timedelta(days=35),
                "response_date": now - timedelta(days=10),
                "reference_number": "FDA-2025-WI-010",
                "questions_submitted": 2,
                "questions_answered": 2,
                "outcome_favorable": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "meeting_minutes_filed": False,
                "managed_by": "Dr. Sarah Chen",
                "attendees": [],
                "notes": "FDA confirmed current PSUR format is acceptable. No changes needed.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "AC-012",
                "trial_id": LIBTAYO_TRIAL,
                "communication_type": CommunicationType.SCIENTIFIC_ADVICE,
                "authority": "NMPA",
                "region": RegionScope.CHINA_NMPA,
                "subject": "NMPA Pre-IND Consultation for LIBTAYO China Registration Trial",
                "communication_date": now - timedelta(days=45),
                "response_date": now - timedelta(days=20),
                "reference_number": "NMPA-2025-SA-011",
                "questions_submitted": 6,
                "questions_answered": 6,
                "outcome_favorable": True,
                "follow_up_required": False,
                "follow_up_date": None,
                "meeting_minutes_filed": True,
                "managed_by": "Dr. Angela Park",
                "attendees": ["Dr. Angela Park", "China Regulatory Director", "NMPA CDE Reviewers"],
                "notes": "NMPA accepted proposed China bridging design with 100-patient enrollment target.",
                "created_at": now - timedelta(days=45),
            },
        ]

        for c in communication_data:
            self._authority_communications[c["id"]] = AuthorityCommunication(**c)

        # --- 12 Impact Assessments ---
        assessment_data = [
            {
                "id": "IA-001",
                "trial_id": EYLEA_TRIAL,
                "intelligence_id": "LM-001",
                "guideline_id": None,
                "assessment_name": "Impact of FDA Anti-VEGF Biosimilar Guidance on EYLEA Trial",
                "assessment_date": now - timedelta(days=40),
                "impact_level": ImpactLevel.HIGH,
                "affected_areas": ["Protocol Design", "Endpoint Selection", "Comparator Strategy"],
                "protocol_change_needed": True,
                "submission_update_needed": True,
                "training_update_needed": False,
                "estimated_cost_impact": 450000.0,
                "estimated_timeline_impact_weeks": 8,
                "risk_mitigation": "Early engagement with FDA via Type B meeting. Pre-specify biosimilar comparator provisions.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Sarah Chen",
                "approved_by": "VP Regulatory Affairs",
                "notes": "High impact but manageable with proactive FDA engagement.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "IA-002",
                "trial_id": EYLEA_TRIAL,
                "intelligence_id": None,
                "guideline_id": "GT-001",
                "assessment_name": "ICH E6(R3) Implementation Impact on EYLEA Operations",
                "assessment_date": now - timedelta(days=170),
                "impact_level": ImpactLevel.HIGH,
                "affected_areas": ["Site Operations", "Monitoring", "TMF Management", "Training"],
                "protocol_change_needed": False,
                "submission_update_needed": False,
                "training_update_needed": True,
                "estimated_cost_impact": 280000.0,
                "estimated_timeline_impact_weeks": 4,
                "risk_mitigation": "Phased implementation plan. Training roll-out across all sites in 3 waves.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. James Wright",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Operational changes primarily. No protocol amendment required.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "IA-003",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_id": "LM-003",
                "guideline_id": None,
                "assessment_name": "FDA Biomarker Guidance Impact on DUPIXENT Stratification",
                "assessment_date": now - timedelta(days=55),
                "impact_level": ImpactLevel.MODERATE,
                "affected_areas": ["Protocol Design", "Biomarker Strategy", "Lab Services"],
                "protocol_change_needed": True,
                "submission_update_needed": False,
                "training_update_needed": True,
                "estimated_cost_impact": 320000.0,
                "estimated_timeline_impact_weeks": 6,
                "risk_mitigation": "Biomarker panel already partially integrated. Expand existing strategy.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "Moderate impact. Aligns with existing biomarker program.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "IA-004",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_id": None,
                "guideline_id": "GT-004",
                "assessment_name": "EMA PRO Co-Primary Endpoint Requirement Impact",
                "assessment_date": now - timedelta(days=55),
                "impact_level": ImpactLevel.HIGH,
                "affected_areas": ["Protocol Design", "Statistical Analysis", "EU Submission"],
                "protocol_change_needed": True,
                "submission_update_needed": True,
                "training_update_needed": True,
                "estimated_cost_impact": 550000.0,
                "estimated_timeline_impact_weeks": 10,
                "risk_mitigation": "Early protocol amendment. DLQI already collected; upgrade to co-primary status.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Robert Kim",
                "approved_by": "VP Regulatory Affairs",
                "notes": "Major impact on EU regulatory strategy. Protocol amendment v3.1 initiated.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "IA-005",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_id": "LM-005",
                "guideline_id": None,
                "assessment_name": "CRO Data Integrity Warning Letter Impact on LIBTAYO Sites",
                "assessment_date": now - timedelta(days=28),
                "impact_level": ImpactLevel.CRITICAL,
                "affected_areas": ["Site Operations", "Data Quality", "Regulatory Compliance", "Audit"],
                "protocol_change_needed": False,
                "submission_update_needed": False,
                "training_update_needed": True,
                "estimated_cost_impact": 750000.0,
                "estimated_timeline_impact_weeks": 12,
                "risk_mitigation": "Immediate for-cause audit of affected sites. CRO transition plan for 3 sites if needed.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Angela Park",
                "approved_by": "Chief Medical Officer",
                "notes": "Critical urgency. Audit team deployed to affected sites within 48 hours.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "IA-006",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_id": "LM-007",
                "guideline_id": None,
                "assessment_name": "MHRA irAE Monitoring Advisory Impact on UK Sites",
                "assessment_date": now - timedelta(days=18),
                "impact_level": ImpactLevel.MODERATE,
                "affected_areas": ["Safety Monitoring", "Site Operations", "Training"],
                "protocol_change_needed": False,
                "submission_update_needed": False,
                "training_update_needed": True,
                "estimated_cost_impact": 120000.0,
                "estimated_timeline_impact_weeks": 3,
                "risk_mitigation": "Update irAE monitoring SOP for UK sites. Additional investigator training.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Pending approval. Draft SOP revision circulated to UK PIs.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "IA-007",
                "trial_id": EYLEA_TRIAL,
                "intelligence_id": "LM-011",
                "guideline_id": None,
                "assessment_name": "EMA PRAC Safety Signal Review Impact on EYLEA Program",
                "assessment_date": now - timedelta(days=8),
                "impact_level": ImpactLevel.HIGH,
                "affected_areas": ["Safety Database", "Regulatory Submissions", "DSUR Preparation"],
                "protocol_change_needed": False,
                "submission_update_needed": True,
                "training_update_needed": False,
                "estimated_cost_impact": 200000.0,
                "estimated_timeline_impact_weeks": 6,
                "risk_mitigation": "Prepare comprehensive safety analysis for PRAC review. Proactive DSUR update.",
                "stakeholders_notified": False,
                "assessed_by": "Dr. James Wright",
                "approved_by": None,
                "notes": "Assessment in progress. Safety data extraction underway.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "IA-008",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_id": "LM-004",
                "guideline_id": None,
                "assessment_name": "ICH E9(R1) Estimand Framework Implementation Impact",
                "assessment_date": now - timedelta(days=110),
                "impact_level": ImpactLevel.MODERATE,
                "affected_areas": ["Statistical Analysis", "SAP", "Regulatory Submissions"],
                "protocol_change_needed": False,
                "submission_update_needed": True,
                "training_update_needed": True,
                "estimated_cost_impact": 180000.0,
                "estimated_timeline_impact_weeks": 4,
                "risk_mitigation": "SAP revision to incorporate estimand framework. Biostatistics team training completed.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Maria Lopez",
                "notes": "On track. SAP revision expected within 2 weeks.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "IA-009",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_id": None,
                "guideline_id": "GT-012",
                "assessment_name": "NMPA Immuno-Oncology Guidelines Impact on China Strategy",
                "assessment_date": now - timedelta(days=12),
                "impact_level": ImpactLevel.HIGH,
                "affected_areas": ["China Registration", "Companion Diagnostic", "Protocol Design", "Lab Services"],
                "protocol_change_needed": True,
                "submission_update_needed": True,
                "training_update_needed": True,
                "estimated_cost_impact": 650000.0,
                "estimated_timeline_impact_weeks": 16,
                "risk_mitigation": "Engage China CRO for PD-L1 lab qualification. Partner with CDx manufacturer.",
                "stakeholders_notified": False,
                "assessed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Major strategic impact. Cross-functional alignment meeting needed.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "IA-010",
                "trial_id": EYLEA_TRIAL,
                "intelligence_id": None,
                "guideline_id": "GT-007",
                "assessment_name": "FDA Retinal Endpoint Guidance Impact on Reading Center",
                "assessment_date": now - timedelta(days=115),
                "impact_level": ImpactLevel.MODERATE,
                "affected_areas": ["Central Reading Center", "Imaging Protocol", "Training"],
                "protocol_change_needed": False,
                "submission_update_needed": False,
                "training_update_needed": True,
                "estimated_cost_impact": 95000.0,
                "estimated_timeline_impact_weeks": 3,
                "risk_mitigation": "Reading center contract amendment. Updated OCT certification standards.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Sarah Chen",
                "approved_by": "Dr. James Wright",
                "notes": "Remediation largely complete. Final reading center certification pending.",
                "created_at": now - timedelta(days=115),
            },
            {
                "id": "IA-011",
                "trial_id": DUPIXENT_TRIAL,
                "intelligence_id": None,
                "guideline_id": "GT-011",
                "assessment_name": "PMDA Biologics Guidance Impact on Japan Development Plan",
                "assessment_date": now - timedelta(days=75),
                "impact_level": ImpactLevel.MODERATE,
                "affected_areas": ["Japan Regulatory", "Immunogenicity Testing", "SAP"],
                "protocol_change_needed": False,
                "submission_update_needed": True,
                "training_update_needed": True,
                "estimated_cost_impact": 210000.0,
                "estimated_timeline_impact_weeks": 5,
                "risk_mitigation": "Add Japanese subgroup analyses. Extend immunogenicity sampling at Japanese sites.",
                "stakeholders_notified": True,
                "assessed_by": "Dr. Robert Kim",
                "approved_by": "Dr. Maria Lopez",
                "notes": "Japan-specific SAP addendum in preparation.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "IA-012",
                "trial_id": LIBTAYO_TRIAL,
                "intelligence_id": "LM-010",
                "guideline_id": None,
                "assessment_name": "NMPA Accelerated Approval Policy Impact Assessment",
                "assessment_date": now - timedelta(days=30),
                "impact_level": ImpactLevel.LOW,
                "affected_areas": ["China Regulatory Strategy"],
                "protocol_change_needed": False,
                "submission_update_needed": False,
                "training_update_needed": False,
                "estimated_cost_impact": 0.0,
                "estimated_timeline_impact_weeks": 0,
                "risk_mitigation": "No immediate action needed. Monitor for final policy details.",
                "stakeholders_notified": False,
                "assessed_by": "Dr. Angela Park",
                "approved_by": None,
                "notes": "Low impact. Informational only for future planning.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for a in assessment_data:
            self._impact_assessments[a["id"]] = ImpactAssessment(**a)

        # --- 12 Compliance Alerts ---
        alert_data = [
            {
                "id": "CA-001",
                "trial_id": EYLEA_TRIAL,
                "alert_title": "ICH E6(R3) Compliance Gap: Risk-Based Monitoring Not Fully Implemented",
                "severity": AlertSeverity.ACTION_REQUIRED,
                "region": RegionScope.GLOBAL,
                "source_intelligence_id": None,
                "description": "Gap assessment reveals risk-based monitoring approach not fully implemented per ICH E6(R3) requirements at 40% of trial sites.",
                "alert_date": now - timedelta(days=160),
                "response_deadline": now - timedelta(days=100),
                "acknowledged": True,
                "acknowledged_by": "Dr. Sarah Chen",
                "acknowledged_date": now - timedelta(days=158),
                "resolved": True,
                "resolved_date": now - timedelta(days=95),
                "resolution_details": "Risk-based monitoring SOP deployed to all sites. Training completed for 100% of CRAs.",
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. James Wright",
                "notes": "Resolved ahead of deadline.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "CA-002",
                "trial_id": EYLEA_TRIAL,
                "alert_title": "EMA PRAC Safety Signal: Urgent Data Review Required",
                "severity": AlertSeverity.URGENT,
                "region": RegionScope.EU_EMA,
                "source_intelligence_id": "LM-011",
                "description": "EMA PRAC initiated safety signal review for thromboembolic events. EYLEA trial data review required within 30 days.",
                "alert_date": now - timedelta(days=10),
                "response_deadline": now + timedelta(days=20),
                "acknowledged": True,
                "acknowledged_by": "Dr. Sarah Chen",
                "acknowledged_date": now - timedelta(days=9),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": True,
                "escalated_to": "VP Clinical Safety",
                "created_by": "Dr. James Wright",
                "notes": "Safety data extraction in progress. DSUR addendum being prepared.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CA-003",
                "trial_id": DUPIXENT_TRIAL,
                "alert_title": "EMA PRO Co-Primary Endpoint Protocol Amendment Required",
                "severity": AlertSeverity.ACTION_REQUIRED,
                "region": RegionScope.EU_EMA,
                "source_intelligence_id": None,
                "description": "EMA CHMP revised guideline requires PRO co-primary endpoint for atopic dermatitis trials. Protocol amendment needed for EU submission.",
                "alert_date": now - timedelta(days=55),
                "response_deadline": now + timedelta(days=30),
                "acknowledged": True,
                "acknowledged_by": "Dr. Maria Lopez",
                "acknowledged_date": now - timedelta(days=53),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Robert Kim",
                "notes": "Protocol amendment v3.1 in preparation. Expected IRB submission within 4 weeks.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CA-004",
                "trial_id": DUPIXENT_TRIAL,
                "alert_title": "ICH E9(R1) Estimand Framework SAP Update Deadline",
                "severity": AlertSeverity.WARNING,
                "region": RegionScope.GLOBAL,
                "source_intelligence_id": "LM-004",
                "description": "SAP must incorporate estimand framework per ICH E9(R1) before database lock. Deadline approaching.",
                "alert_date": now - timedelta(days=100),
                "response_deadline": now + timedelta(days=60),
                "acknowledged": True,
                "acknowledged_by": "Dr. Robert Kim",
                "acknowledged_date": now - timedelta(days=98),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Robert Kim",
                "notes": "SAP revision 70% complete. On track for deadline.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "CA-005",
                "trial_id": LIBTAYO_TRIAL,
                "alert_title": "CRITICAL: CRO Data Integrity Issue at 3 LIBTAYO Sites",
                "severity": AlertSeverity.EMERGENCY,
                "region": RegionScope.US_FDA,
                "source_intelligence_id": "LM-005",
                "description": "FDA warning letter to CRO affects 3 LIBTAYO trial sites. For-cause audit required immediately. Potential data integrity risk.",
                "alert_date": now - timedelta(days=28),
                "response_deadline": now - timedelta(days=14),
                "acknowledged": True,
                "acknowledged_by": "Dr. Angela Park",
                "acknowledged_date": now - timedelta(days=28),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": True,
                "escalated_to": "Chief Medical Officer",
                "created_by": "Dr. Angela Park",
                "notes": "Audit team deployed. Preliminary findings: 2 of 3 sites show minor GCP deviations only. Full report in 2 weeks.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CA-006",
                "trial_id": LIBTAYO_TRIAL,
                "alert_title": "MHRA irAE Monitoring SOP Update Required for UK Sites",
                "severity": AlertSeverity.ACTION_REQUIRED,
                "region": RegionScope.UK_MHRA,
                "source_intelligence_id": "LM-007",
                "description": "MHRA advisory requires enhanced immune-related adverse event monitoring at UK trial sites. SOP update and retraining needed.",
                "alert_date": now - timedelta(days=18),
                "response_deadline": now + timedelta(days=27),
                "acknowledged": True,
                "acknowledged_by": "Dr. Angela Park",
                "acknowledged_date": now - timedelta(days=17),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Angela Park",
                "notes": "Draft SOP revision completed. Pending PI review at UK sites.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "CA-007",
                "trial_id": EYLEA_TRIAL,
                "alert_title": "FDA Retinal Endpoint Reading Center Certification Gap",
                "severity": AlertSeverity.WARNING,
                "region": RegionScope.US_FDA,
                "source_intelligence_id": None,
                "description": "Central reading center certification needs update per new FDA retinal endpoint guidance. Current certification expires in 30 days.",
                "alert_date": now - timedelta(days=110),
                "response_deadline": now - timedelta(days=80),
                "acknowledged": True,
                "acknowledged_by": "Dr. James Wright",
                "acknowledged_date": now - timedelta(days=109),
                "resolved": True,
                "resolved_date": now - timedelta(days=85),
                "resolution_details": "Reading center recertified under new FDA standards. Contract amendment executed.",
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Sarah Chen",
                "notes": "Resolved. New certification valid for 2 years.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "CA-008",
                "trial_id": DUPIXENT_TRIAL,
                "alert_title": "PMDA Japanese Subgroup Analysis Requirement",
                "severity": AlertSeverity.WARNING,
                "region": RegionScope.JAPAN_PMDA,
                "source_intelligence_id": None,
                "description": "PMDA updated guidance requires Japanese-specific subgroup analysis and extended immunogenicity sampling. SAP addendum needed.",
                "alert_date": now - timedelta(days=75),
                "response_deadline": now + timedelta(days=15),
                "acknowledged": True,
                "acknowledged_by": "Dr. Robert Kim",
                "acknowledged_date": now - timedelta(days=73),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Maria Lopez",
                "notes": "SAP addendum in final review. Japanese CRA team briefed.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "CA-009",
                "trial_id": LIBTAYO_TRIAL,
                "alert_title": "NMPA Companion Diagnostic Co-Development Requirement",
                "severity": AlertSeverity.ACTION_REQUIRED,
                "region": RegionScope.CHINA_NMPA,
                "source_intelligence_id": None,
                "description": "New NMPA guidelines require companion diagnostic co-development for PD-1/PD-L1 inhibitor registrations in China.",
                "alert_date": now - timedelta(days=12),
                "response_deadline": now + timedelta(days=108),
                "acknowledged": True,
                "acknowledged_by": "Dr. Angela Park",
                "acknowledged_date": now - timedelta(days=11),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Angela Park",
                "notes": "Cross-functional team formed. CDx partner evaluation underway.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CA-010",
                "trial_id": EYLEA_TRIAL,
                "alert_title": "Anti-VEGF Biosimilar Guidance: Comparator Strategy Review",
                "severity": AlertSeverity.INFORMATIONAL,
                "region": RegionScope.US_FDA,
                "source_intelligence_id": "LM-001",
                "description": "FDA draft guidance on anti-VEGF biosimilar development may require updates to EYLEA trial comparator strategy for future studies.",
                "alert_date": now - timedelta(days=42),
                "response_deadline": None,
                "acknowledged": True,
                "acknowledged_by": "Dr. Sarah Chen",
                "acknowledged_date": now - timedelta(days=40),
                "resolved": True,
                "resolved_date": now - timedelta(days=35),
                "resolution_details": "Reviewed with FDA in Type B meeting. Current comparator approach acceptable for ongoing trial.",
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Sarah Chen",
                "notes": "No action required for current trial. Monitor for final guidance.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "CA-011",
                "trial_id": DUPIXENT_TRIAL,
                "alert_title": "Biomarker Stratification Protocol Update Needed",
                "severity": AlertSeverity.WARNING,
                "region": RegionScope.US_FDA,
                "source_intelligence_id": "LM-003",
                "description": "FDA guidance on biomarker-driven AD trials recommends Type 2 inflammatory biomarker stratification. Protocol update advisable.",
                "alert_date": now - timedelta(days=50),
                "response_deadline": now + timedelta(days=40),
                "acknowledged": True,
                "acknowledged_by": "Dr. Maria Lopez",
                "acknowledged_date": now - timedelta(days=48),
                "resolved": False,
                "resolved_date": None,
                "resolution_details": None,
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Maria Lopez",
                "notes": "Biomarker stratification plan drafted. Aligns with existing sample collection.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CA-012",
                "trial_id": LIBTAYO_TRIAL,
                "alert_title": "Project Orbis Expedited Review Opportunity",
                "severity": AlertSeverity.INFORMATIONAL,
                "region": RegionScope.GLOBAL,
                "source_intelligence_id": "LM-006",
                "description": "FDA Project Orbis now includes CSCC. Opportunity for concurrent multi-regional submission and expedited review.",
                "alert_date": now - timedelta(days=70),
                "response_deadline": None,
                "acknowledged": True,
                "acknowledged_by": "Dr. Angela Park",
                "acknowledged_date": now - timedelta(days=68),
                "resolved": True,
                "resolved_date": now - timedelta(days=60),
                "resolution_details": "Project Orbis application submitted. Accepted for concurrent review with FDA, TGA, and Health Canada.",
                "escalated": False,
                "escalated_to": None,
                "created_by": "Dr. Angela Park",
                "notes": "Positive development. Expected to accelerate global approval timeline by 6-9 months.",
                "created_at": now - timedelta(days=70),
            },
        ]

        for al in alert_data:
            self._compliance_alerts[al["id"]] = ComplianceAlert(**al)

    # ------------------------------------------------------------------
    # Landscape Monitors
    # ------------------------------------------------------------------

    def list_landscape_monitors(
        self,
        *,
        trial_id: str | None = None,
        intelligence_type: IntelligenceType | None = None,
        region: RegionScope | None = None,
        impact_level: ImpactLevel | None = None,
    ) -> list[LandscapeMonitor]:
        """List landscape monitors with optional filters."""
        with self._lock:
            result = list(self._landscape_monitors.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if intelligence_type is not None:
            result = [m for m in result if m.intelligence_type == intelligence_type]
        if region is not None:
            result = [m for m in result if m.region == region]
        if impact_level is not None:
            result = [m for m in result if m.impact_level == impact_level]

        return sorted(result, key=lambda m: m.publication_date, reverse=True)

    def get_landscape_monitor(self, monitor_id: str) -> LandscapeMonitor | None:
        """Get a single landscape monitor by ID."""
        with self._lock:
            return self._landscape_monitors.get(monitor_id)

    def create_landscape_monitor(self, payload: LandscapeMonitorCreate) -> LandscapeMonitor:
        """Create a new landscape monitor."""
        now = datetime.now(timezone.utc)
        monitor_id = f"LM-{uuid4().hex[:8].upper()}"
        monitor = LandscapeMonitor(
            id=monitor_id,
            trial_id=payload.trial_id,
            intelligence_type=payload.intelligence_type,
            region=payload.region,
            title=payload.title,
            description=payload.description,
            source_url=None,
            publication_date=payload.publication_date,
            effective_date=None,
            impact_level=payload.impact_level,
            therapeutic_area=None,
            drug_class_affected=None,
            action_required=False,
            action_deadline=None,
            analyzed=False,
            analyzed_by=None,
            analysis_date=None,
            monitored_by=payload.monitored_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._landscape_monitors[monitor_id] = monitor
        logger.info("Created landscape monitor %s for trial %s", monitor_id, payload.trial_id)
        return monitor

    def update_landscape_monitor(
        self, monitor_id: str, payload: LandscapeMonitorUpdate
    ) -> LandscapeMonitor | None:
        """Update an existing landscape monitor."""
        with self._lock:
            existing = self._landscape_monitors.get(monitor_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = LandscapeMonitor(**data)
            self._landscape_monitors[monitor_id] = updated
        return updated

    def delete_landscape_monitor(self, monitor_id: str) -> bool:
        """Delete a landscape monitor. Returns True if deleted."""
        with self._lock:
            if monitor_id in self._landscape_monitors:
                del self._landscape_monitors[monitor_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Guideline Trackers
    # ------------------------------------------------------------------

    def list_guideline_trackers(
        self,
        *,
        trial_id: str | None = None,
        region: RegionScope | None = None,
        compliance_gap_identified: bool | None = None,
    ) -> list[GuidelineTracker]:
        """List guideline trackers with optional filters."""
        with self._lock:
            result = list(self._guideline_trackers.values())

        if trial_id is not None:
            result = [g for g in result if g.trial_id == trial_id]
        if region is not None:
            result = [g for g in result if g.region == region]
        if compliance_gap_identified is not None:
            result = [g for g in result if g.compliance_gap_identified == compliance_gap_identified]

        return sorted(result, key=lambda g: g.effective_date, reverse=True)

    def get_guideline_tracker(self, tracker_id: str) -> GuidelineTracker | None:
        """Get a single guideline tracker by ID."""
        with self._lock:
            return self._guideline_trackers.get(tracker_id)

    def create_guideline_tracker(self, payload: GuidelineTrackerCreate) -> GuidelineTracker:
        """Create a new guideline tracker."""
        now = datetime.now(timezone.utc)
        tracker_id = f"GT-{uuid4().hex[:8].upper()}"
        tracker = GuidelineTracker(
            id=tracker_id,
            trial_id=payload.trial_id,
            guideline_name=payload.guideline_name,
            issuing_authority=payload.issuing_authority,
            region=payload.region,
            version=payload.version,
            effective_date=payload.effective_date,
            supersedes_version=None,
            key_changes=[],
            impact_on_protocol=False,
            impact_on_operations=False,
            compliance_gap_identified=False,
            remediation_plan=None,
            remediation_deadline=None,
            tracked_by=payload.tracked_by,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._guideline_trackers[tracker_id] = tracker
        logger.info("Created guideline tracker %s for trial %s", tracker_id, payload.trial_id)
        return tracker

    def update_guideline_tracker(
        self, tracker_id: str, payload: GuidelineTrackerUpdate
    ) -> GuidelineTracker | None:
        """Update an existing guideline tracker."""
        with self._lock:
            existing = self._guideline_trackers.get(tracker_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = GuidelineTracker(**data)
            self._guideline_trackers[tracker_id] = updated
        return updated

    def delete_guideline_tracker(self, tracker_id: str) -> bool:
        """Delete a guideline tracker. Returns True if deleted."""
        with self._lock:
            if tracker_id in self._guideline_trackers:
                del self._guideline_trackers[tracker_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Authority Communications
    # ------------------------------------------------------------------

    def list_authority_communications(
        self,
        *,
        trial_id: str | None = None,
        communication_type: CommunicationType | None = None,
        region: RegionScope | None = None,
    ) -> list[AuthorityCommunication]:
        """List authority communications with optional filters."""
        with self._lock:
            result = list(self._authority_communications.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if communication_type is not None:
            result = [c for c in result if c.communication_type == communication_type]
        if region is not None:
            result = [c for c in result if c.region == region]

        return sorted(result, key=lambda c: c.communication_date, reverse=True)

    def get_authority_communication(self, communication_id: str) -> AuthorityCommunication | None:
        """Get a single authority communication by ID."""
        with self._lock:
            return self._authority_communications.get(communication_id)

    def create_authority_communication(
        self, payload: AuthorityCommunicationCreate
    ) -> AuthorityCommunication:
        """Create a new authority communication."""
        now = datetime.now(timezone.utc)
        comm_id = f"AC-{uuid4().hex[:8].upper()}"
        comm = AuthorityCommunication(
            id=comm_id,
            trial_id=payload.trial_id,
            communication_type=payload.communication_type,
            authority=payload.authority,
            region=payload.region,
            subject=payload.subject,
            communication_date=payload.communication_date,
            response_date=None,
            reference_number=None,
            questions_submitted=0,
            questions_answered=0,
            outcome_favorable=None,
            follow_up_required=False,
            follow_up_date=None,
            meeting_minutes_filed=False,
            managed_by=payload.managed_by,
            attendees=[],
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._authority_communications[comm_id] = comm
        logger.info("Created authority communication %s for trial %s", comm_id, payload.trial_id)
        return comm

    def update_authority_communication(
        self, communication_id: str, payload: AuthorityCommunicationUpdate
    ) -> AuthorityCommunication | None:
        """Update an existing authority communication."""
        with self._lock:
            existing = self._authority_communications.get(communication_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AuthorityCommunication(**data)
            self._authority_communications[communication_id] = updated
        return updated

    def delete_authority_communication(self, communication_id: str) -> bool:
        """Delete an authority communication. Returns True if deleted."""
        with self._lock:
            if communication_id in self._authority_communications:
                del self._authority_communications[communication_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Impact Assessments
    # ------------------------------------------------------------------

    def list_impact_assessments(
        self,
        *,
        trial_id: str | None = None,
        impact_level: ImpactLevel | None = None,
    ) -> list[ImpactAssessment]:
        """List impact assessments with optional filters."""
        with self._lock:
            result = list(self._impact_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if impact_level is not None:
            result = [a for a in result if a.impact_level == impact_level]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_impact_assessment(self, assessment_id: str) -> ImpactAssessment | None:
        """Get a single impact assessment by ID."""
        with self._lock:
            return self._impact_assessments.get(assessment_id)

    def create_impact_assessment(self, payload: ImpactAssessmentCreate) -> ImpactAssessment:
        """Create a new impact assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"IA-{uuid4().hex[:8].upper()}"
        assessment = ImpactAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            intelligence_id=payload.intelligence_id,
            guideline_id=payload.guideline_id,
            assessment_name=payload.assessment_name,
            assessment_date=now,
            impact_level=payload.impact_level,
            affected_areas=[],
            protocol_change_needed=False,
            submission_update_needed=False,
            training_update_needed=False,
            estimated_cost_impact=0.0,
            estimated_timeline_impact_weeks=0,
            risk_mitigation=None,
            stakeholders_notified=False,
            assessed_by=payload.assessed_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._impact_assessments[assessment_id] = assessment
        logger.info("Created impact assessment %s for trial %s", assessment_id, payload.trial_id)
        return assessment

    def update_impact_assessment(
        self, assessment_id: str, payload: ImpactAssessmentUpdate
    ) -> ImpactAssessment | None:
        """Update an existing impact assessment."""
        with self._lock:
            existing = self._impact_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ImpactAssessment(**data)
            self._impact_assessments[assessment_id] = updated
        return updated

    def delete_impact_assessment(self, assessment_id: str) -> bool:
        """Delete an impact assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._impact_assessments:
                del self._impact_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Alerts
    # ------------------------------------------------------------------

    def list_compliance_alerts(
        self,
        *,
        trial_id: str | None = None,
        severity: AlertSeverity | None = None,
        region: RegionScope | None = None,
        resolved: bool | None = None,
    ) -> list[ComplianceAlert]:
        """List compliance alerts with optional filters."""
        with self._lock:
            result = list(self._compliance_alerts.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if severity is not None:
            result = [a for a in result if a.severity == severity]
        if region is not None:
            result = [a for a in result if a.region == region]
        if resolved is not None:
            result = [a for a in result if a.resolved == resolved]

        return sorted(result, key=lambda a: a.alert_date, reverse=True)

    def get_compliance_alert(self, alert_id: str) -> ComplianceAlert | None:
        """Get a single compliance alert by ID."""
        with self._lock:
            return self._compliance_alerts.get(alert_id)

    def create_compliance_alert(self, payload: ComplianceAlertCreate) -> ComplianceAlert:
        """Create a new compliance alert."""
        now = datetime.now(timezone.utc)
        alert_id = f"CA-{uuid4().hex[:8].upper()}"
        alert = ComplianceAlert(
            id=alert_id,
            trial_id=payload.trial_id,
            alert_title=payload.alert_title,
            severity=payload.severity,
            region=payload.region,
            source_intelligence_id=payload.source_intelligence_id,
            description=payload.description,
            alert_date=now,
            response_deadline=None,
            acknowledged=False,
            acknowledged_by=None,
            acknowledged_date=None,
            resolved=False,
            resolved_date=None,
            resolution_details=None,
            escalated=False,
            escalated_to=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._compliance_alerts[alert_id] = alert
        logger.info("Created compliance alert %s for trial %s", alert_id, payload.trial_id)
        return alert

    def update_compliance_alert(
        self, alert_id: str, payload: ComplianceAlertUpdate
    ) -> ComplianceAlert | None:
        """Update an existing compliance alert."""
        with self._lock:
            existing = self._compliance_alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComplianceAlert(**data)
            self._compliance_alerts[alert_id] = updated
        return updated

    def delete_compliance_alert(self, alert_id: str) -> bool:
        """Delete a compliance alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._compliance_alerts:
                del self._compliance_alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> RegulatoryIntelligenceMetrics:
        """Compute aggregated regulatory intelligence metrics."""
        with self._lock:
            monitors = list(self._landscape_monitors.values())
            guidelines = list(self._guideline_trackers.values())
            communications = list(self._authority_communications.values())
            assessments = list(self._impact_assessments.values())
            alerts = list(self._compliance_alerts.values())

        # Intelligence items by type
        items_by_type: dict[str, int] = {}
        for m in monitors:
            key = m.intelligence_type.value
            items_by_type[key] = items_by_type.get(key, 0) + 1

        # Intelligence items by region
        items_by_region: dict[str, int] = {}
        for m in monitors:
            key = m.region.value
            items_by_region[key] = items_by_region.get(key, 0) + 1

        # Intelligence items by impact
        items_by_impact: dict[str, int] = {}
        for m in monitors:
            key = m.impact_level.value
            items_by_impact[key] = items_by_impact.get(key, 0) + 1

        # Unanalyzed items
        unanalyzed_items = sum(1 for m in monitors if not m.analyzed)

        # Guidelines with gaps
        guidelines_with_gaps = sum(1 for g in guidelines if g.compliance_gap_identified)

        # Communications by type
        communications_by_type: dict[str, int] = {}
        for c in communications:
            key = c.communication_type.value
            communications_by_type[key] = communications_by_type.get(key, 0) + 1

        # Favorable outcomes
        favorable_outcomes = sum(1 for c in communications if c.outcome_favorable is True)

        # High impact assessments
        high_impact_assessments = sum(
            1 for a in assessments if a.impact_level in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)
        )

        # Alerts by severity
        alerts_by_severity: dict[str, int] = {}
        for a in alerts:
            key = a.severity.value
            alerts_by_severity[key] = alerts_by_severity.get(key, 0) + 1

        # Unresolved alerts
        unresolved_alerts = sum(1 for a in alerts if not a.resolved)

        return RegulatoryIntelligenceMetrics(
            total_intelligence_items=len(monitors),
            items_by_type=items_by_type,
            items_by_region=items_by_region,
            items_by_impact=items_by_impact,
            unanalyzed_items=unanalyzed_items,
            total_guidelines=len(guidelines),
            guidelines_with_gaps=guidelines_with_gaps,
            total_communications=len(communications),
            communications_by_type=communications_by_type,
            favorable_outcomes=favorable_outcomes,
            total_impact_assessments=len(assessments),
            high_impact_assessments=high_impact_assessments,
            total_alerts=len(alerts),
            alerts_by_severity=alerts_by_severity,
            unresolved_alerts=unresolved_alerts,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RegulatoryIntelligenceHubService | None = None
_instance_lock = threading.Lock()


def get_regulatory_intelligence_hub_service() -> RegulatoryIntelligenceHubService:
    """Return the singleton RegulatoryIntelligenceHubService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RegulatoryIntelligenceHubService()
    return _instance


def reset_regulatory_intelligence_hub_service() -> RegulatoryIntelligenceHubService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RegulatoryIntelligenceHubService()
    return _instance
