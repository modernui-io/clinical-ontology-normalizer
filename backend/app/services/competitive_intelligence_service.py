"""Competitive Intelligence (CI-INTEL) Service.

Manages competitive intelligence operations including competitor program tracking,
market intelligence gathering, patent landscape monitoring, conference intelligence,
competitive alerts, and positioning metrics.

Usage:
    from app.services.competitive_intelligence_service import (
        get_competitive_intelligence_service,
    )

    svc = get_competitive_intelligence_service()
    programs = svc.list_competitor_programs()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.competitive_intelligence import (
    AlertPriority,
    CompetitiveAlert,
    CompetitiveAlertCreate,
    CompetitiveAlertUpdate,
    CompetitiveIntelligenceMetrics,
    CompetitorProgram,
    CompetitorProgramCreate,
    CompetitorProgramUpdate,
    CompetitorStatus,
    ConferenceIntelligence,
    ConferenceIntelligenceCreate,
    ConferenceIntelligenceUpdate,
    ConferenceType,
    IntelligenceSource,
    MarketIntelligence,
    MarketIntelligenceCreate,
    MarketIntelligenceUpdate,
    PatentLandscape,
    PatentLandscapeCreate,
    PatentLandscapeUpdate,
    PatentStatus,
    ThreatLevel,
)

logger = logging.getLogger(__name__)


class CompetitiveIntelligenceService:
    """In-memory Competitive Intelligence engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._programs: dict[str, CompetitorProgram] = {}
        self._market_intel: dict[str, MarketIntelligence] = {}
        self._patents: dict[str, PatentLandscape] = {}
        self._conference_intel: dict[str, ConferenceIntelligence] = {}
        self._alerts: dict[str, CompetitiveAlert] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic competitive intelligence data for Regeneron drugs."""
        now = datetime.now(timezone.utc)

        # --- Competitor Programs (12 items) ---
        programs_data = [
            {
                "id": "CP-001",
                "competitor_name": "Roche/Genentech",
                "drug_name": "Vabysmo (faricimab)",
                "mechanism_of_action": "Bispecific antibody targeting VEGF-A and Ang-2",
                "therapeutic_area": "Ophthalmology",
                "indication": "Wet AMD",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=900),
                "estimated_approval_date": None,
                "trial_count": 4,
                "patient_enrollment": 3200,
                "threat_level": ThreatLevel.CRITICAL,
                "our_competing_program": "EYLEA HD (aflibercept 8mg)",
                "key_differentiators": ["Bispecific mechanism", "Extended dosing intervals up to 16 weeks", "Dual pathway inhibition"],
                "notes": "Vabysmo approved Jan 2022. Major competitive threat to EYLEA franchise.",
                "last_updated": now - timedelta(days=5),
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "CP-002",
                "competitor_name": "Novartis",
                "drug_name": "Beovu (brolucizumab)",
                "mechanism_of_action": "Anti-VEGF single-chain antibody fragment",
                "therapeutic_area": "Ophthalmology",
                "indication": "Wet AMD",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=1200),
                "estimated_approval_date": None,
                "trial_count": 3,
                "patient_enrollment": 1800,
                "threat_level": ThreatLevel.MODERATE,
                "our_competing_program": "EYLEA HD (aflibercept 8mg)",
                "key_differentiators": ["Smaller molecule size", "Higher molar concentration", "Safety concerns (IOI/vasculitis)"],
                "notes": "Safety signals have limited uptake. Monitoring post-marketing data.",
                "last_updated": now - timedelta(days=10),
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "CP-003",
                "competitor_name": "AbbVie/Reata",
                "drug_name": "Rinvoq (upadacitinib)",
                "mechanism_of_action": "JAK1 selective inhibitor",
                "therapeutic_area": "Dermatology/Immunology",
                "indication": "Atopic Dermatitis",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=800),
                "estimated_approval_date": None,
                "trial_count": 5,
                "patient_enrollment": 4500,
                "threat_level": ThreatLevel.HIGH,
                "our_competing_program": "Dupixent (dupilumab)",
                "key_differentiators": ["Oral administration", "Rapid onset of action", "JAK1 selectivity"],
                "notes": "Oral convenience is key differentiator vs injectable Dupixent. Black box warning mitigates threat.",
                "last_updated": now - timedelta(days=3),
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "CP-004",
                "competitor_name": "Pfizer",
                "drug_name": "Cibinqo (abrocitinib)",
                "mechanism_of_action": "JAK1 inhibitor",
                "therapeutic_area": "Dermatology/Immunology",
                "indication": "Atopic Dermatitis",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=750),
                "estimated_approval_date": None,
                "trial_count": 3,
                "patient_enrollment": 2800,
                "threat_level": ThreatLevel.HIGH,
                "our_competing_program": "Dupixent (dupilumab)",
                "key_differentiators": ["Oral once daily", "Rapid itch relief", "Flexible dosing"],
                "notes": "Direct Dupixent competitor. JAK safety class effect limits market share.",
                "last_updated": now - timedelta(days=7),
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "CP-005",
                "competitor_name": "Merck",
                "drug_name": "Keytruda (pembrolizumab)",
                "mechanism_of_action": "Anti-PD-1 monoclonal antibody",
                "therapeutic_area": "Oncology",
                "indication": "CSCC",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=1500),
                "estimated_approval_date": None,
                "trial_count": 8,
                "patient_enrollment": 12000,
                "threat_level": ThreatLevel.HIGH,
                "our_competing_program": "Libtayo (cemiplimab)",
                "key_differentiators": ["Broadest indication portfolio", "Extensive combination data", "Market leader in IO"],
                "notes": "Market leader in PD-1 space. Libtayo maintains first-mover advantage in CSCC.",
                "last_updated": now - timedelta(days=2),
                "created_at": now - timedelta(days=600),
            },
            {
                "id": "CP-006",
                "competitor_name": "Bristol Myers Squibb",
                "drug_name": "Opdivo (nivolumab)",
                "mechanism_of_action": "Anti-PD-1 monoclonal antibody",
                "therapeutic_area": "Oncology",
                "indication": "NSCLC",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=1400),
                "estimated_approval_date": None,
                "trial_count": 6,
                "patient_enrollment": 9000,
                "threat_level": ThreatLevel.MODERATE,
                "our_competing_program": "Libtayo (cemiplimab)",
                "key_differentiators": ["Combination with Yervoy", "Long-term survival data", "Broad tumor type coverage"],
                "notes": "Established IO competitor. Libtayo differentiated by monotherapy efficacy in CSCC.",
                "last_updated": now - timedelta(days=8),
                "created_at": now - timedelta(days=550),
            },
            {
                "id": "CP-007",
                "competitor_name": "Kodiak Sciences",
                "drug_name": "Tarcocimab (KSI-301)",
                "mechanism_of_action": "Anti-VEGF antibody biopolymer conjugate",
                "therapeutic_area": "Ophthalmology",
                "indication": "Wet AMD / DME",
                "status": CompetitorStatus.PHASE_III,
                "phase_start_date": now - timedelta(days=400),
                "estimated_approval_date": now + timedelta(days=365),
                "trial_count": 3,
                "patient_enrollment": 1500,
                "threat_level": ThreatLevel.MODERATE,
                "our_competing_program": "EYLEA HD (aflibercept 8mg)",
                "key_differentiators": ["ABC Platform technology", "Potential for 6-month dosing", "Novel biopolymer conjugate"],
                "notes": "Phase III DAZZLE results mixed. Monitoring closely.",
                "last_updated": now - timedelta(days=15),
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "CP-008",
                "competitor_name": "Sanofi",
                "drug_name": "Itepekimab",
                "mechanism_of_action": "Anti-IL-33 monoclonal antibody",
                "therapeutic_area": "Respiratory/Immunology",
                "indication": "Asthma (COPD)",
                "status": CompetitorStatus.PHASE_III,
                "phase_start_date": now - timedelta(days=200),
                "estimated_approval_date": now + timedelta(days=600),
                "trial_count": 2,
                "patient_enrollment": 900,
                "threat_level": ThreatLevel.LOW,
                "our_competing_program": "Dupixent (dupilumab)",
                "key_differentiators": ["IL-33 pathway", "Potential combination with Dupixent", "Novel upstream target"],
                "notes": "Partnered program. Could complement Dupixent rather than compete directly.",
                "last_updated": now - timedelta(days=20),
                "created_at": now - timedelta(days=250),
            },
            {
                "id": "CP-009",
                "competitor_name": "Arcus Biosciences",
                "drug_name": "Domvanalimab",
                "mechanism_of_action": "Anti-TIGIT monoclonal antibody",
                "therapeutic_area": "Oncology",
                "indication": "NSCLC",
                "status": CompetitorStatus.PHASE_III,
                "phase_start_date": now - timedelta(days=180),
                "estimated_approval_date": now + timedelta(days=500),
                "trial_count": 2,
                "patient_enrollment": 700,
                "threat_level": ThreatLevel.LOW,
                "our_competing_program": "Libtayo (cemiplimab)",
                "key_differentiators": ["TIGIT checkpoint", "Combination with PD-1", "Novel checkpoint target"],
                "notes": "Early but potentially disruptive. TIGIT class results mixed across industry.",
                "last_updated": now - timedelta(days=25),
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "CP-010",
                "competitor_name": "Apellis Pharmaceuticals",
                "drug_name": "Syfovre (pegcetacoplan)",
                "mechanism_of_action": "Complement C3 inhibitor",
                "therapeutic_area": "Ophthalmology",
                "indication": "Geographic Atrophy",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=600),
                "estimated_approval_date": None,
                "trial_count": 2,
                "patient_enrollment": 1200,
                "threat_level": ThreatLevel.MODERATE,
                "our_competing_program": "EYLEA HD (aflibercept 8mg)",
                "key_differentiators": ["First GA treatment approved", "Complement pathway", "Monthly/EOM dosing"],
                "notes": "Different indication (GA vs wet AMD) but adjacent competitive space. Monitoring.",
                "last_updated": now - timedelta(days=12),
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "CP-011",
                "competitor_name": "Eli Lilly",
                "drug_name": "Lebrikizumab",
                "mechanism_of_action": "Anti-IL-13 monoclonal antibody",
                "therapeutic_area": "Dermatology/Immunology",
                "indication": "Atopic Dermatitis",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=500),
                "estimated_approval_date": None,
                "trial_count": 4,
                "patient_enrollment": 2500,
                "threat_level": ThreatLevel.HIGH,
                "our_competing_program": "Dupixent (dupilumab)",
                "key_differentiators": ["IL-13 specific targeting", "Monthly maintenance dosing", "Injectable biologic"],
                "notes": "Approved in EU/US. Direct biologic competitor to Dupixent in AD space.",
                "last_updated": now - timedelta(days=4),
                "created_at": now - timedelta(days=320),
            },
            {
                "id": "CP-012",
                "competitor_name": "Astellas/Seagen",
                "drug_name": "Padcev (enfortumab vedotin)",
                "mechanism_of_action": "Antibody-drug conjugate targeting Nectin-4",
                "therapeutic_area": "Oncology",
                "indication": "Urothelial Cancer",
                "status": CompetitorStatus.APPROVED,
                "phase_start_date": now - timedelta(days=700),
                "estimated_approval_date": None,
                "trial_count": 3,
                "patient_enrollment": 1600,
                "threat_level": ThreatLevel.LOW,
                "our_competing_program": "Libtayo (cemiplimab)",
                "key_differentiators": ["ADC mechanism", "Combination with Keytruda", "Different MOA class"],
                "notes": "ADC + IO combination data strong. Monitoring cross-tumor implications for Libtayo.",
                "last_updated": now - timedelta(days=18),
                "created_at": now - timedelta(days=280),
            },
        ]

        for p in programs_data:
            self._programs[p["id"]] = CompetitorProgram(**p)

        # --- Market Intelligence (5 items) ---
        market_intel_data = [
            {
                "id": "MI-001",
                "source": IntelligenceSource.SEC_FILING,
                "title": "Roche Q4 2025 Earnings: Vabysmo Revenue Exceeds $4B Annually",
                "summary": "Roche reported Vabysmo global sales exceeding $4B in 2025, driven by strong uptake in wet AMD and DME. Market share gains primarily from Lucentis conversions.",
                "competitor_name": "Roche/Genentech",
                "therapeutic_area": "Ophthalmology",
                "event_date": now - timedelta(days=30),
                "impact_assessment": "Significant competitive pressure on EYLEA franchise. EYLEA HD differentiation messaging critical.",
                "threat_level": ThreatLevel.HIGH,
                "action_required": True,
                "action_items": ["Update competitive positioning deck", "Brief field medical team", "Prepare market access response"],
                "source_url": "https://www.roche.com/investors/reports",
                "analyzed_by": "Strategic Intelligence Team",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "MI-002",
                "source": IntelligenceSource.PRESS_RELEASE,
                "title": "AbbVie Reports Rinvoq AD Market Share Growth in Q4",
                "summary": "AbbVie press release indicates Rinvoq gaining market share in moderate-to-severe AD segment, particularly in JAK-eligible patients who prefer oral therapy.",
                "competitor_name": "AbbVie",
                "therapeutic_area": "Dermatology/Immunology",
                "event_date": now - timedelta(days=45),
                "impact_assessment": "Oral JAK inhibitors continue to segment the AD market. Dupixent maintains biologic leadership but oral convenience remains a differentiator.",
                "threat_level": ThreatLevel.MODERATE,
                "action_required": False,
                "action_items": [],
                "source_url": "https://news.abbvie.com",
                "analyzed_by": "Immunology CI Lead",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "MI-003",
                "source": IntelligenceSource.FDA_DATABASE,
                "title": "FDA Approves Lebrikizumab for Atopic Dermatitis",
                "summary": "Eli Lilly receives FDA approval for lebrikizumab (Ebglyss) for moderate-to-severe atopic dermatitis in adults and adolescents. Monthly maintenance dosing.",
                "competitor_name": "Eli Lilly",
                "therapeutic_area": "Dermatology/Immunology",
                "event_date": now - timedelta(days=60),
                "impact_assessment": "New biologic competitor to Dupixent. IL-13 specific mechanism and monthly dosing are key differentiators. Market impact expected within 6 months.",
                "threat_level": ThreatLevel.HIGH,
                "action_required": True,
                "action_items": ["Update competitive landscape analysis", "Prepare medical education materials", "Review patient switching data"],
                "source_url": "https://www.fda.gov/drugs/new-drugs-fda-cders-new-molecular-entities-and-new-therapeutic-biological-products",
                "analyzed_by": "Regulatory Intelligence",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "MI-004",
                "source": IntelligenceSource.CLINICAL_TRIALS_GOV,
                "title": "Kodiak KSI-301 Phase III DAZZLE Top-Line Results",
                "summary": "Kodiak Sciences announces DAZZLE Phase III top-line results for KSI-301 in wet AMD. Primary endpoint met but mixed secondary outcomes. Durability data pending.",
                "competitor_name": "Kodiak Sciences",
                "therapeutic_area": "Ophthalmology",
                "event_date": now - timedelta(days=90),
                "impact_assessment": "Mixed results reduce near-term competitive threat. Long-term durability data will determine commercial viability.",
                "threat_level": ThreatLevel.LOW,
                "action_required": False,
                "action_items": [],
                "source_url": "https://clinicaltrials.gov",
                "analyzed_by": "Ophthalmology CI Lead",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "MI-005",
                "source": IntelligenceSource.ANALYST_REPORT,
                "title": "Morgan Stanley IO Market Landscape 2026 Outlook",
                "summary": "Analyst report forecasts PD-1/PD-L1 market to reach $60B by 2028. Keytruda maintains dominance. Libtayo noted for strong CSCC positioning.",
                "competitor_name": None,
                "therapeutic_area": "Oncology",
                "event_date": now - timedelta(days=20),
                "impact_assessment": "Favorable positioning for Libtayo in CSCC niche. Broader IO expansion opportunities identified.",
                "threat_level": ThreatLevel.LOW,
                "action_required": False,
                "action_items": [],
                "source_url": None,
                "analyzed_by": "Oncology Strategy Team",
                "created_at": now - timedelta(days=18),
            },
        ]

        for mi in market_intel_data:
            self._market_intel[mi["id"]] = MarketIntelligence(**mi)

        # --- Patent Landscape (4 items) ---
        patents_data = [
            {
                "id": "PAT-001",
                "patent_number": "US11,345,678",
                "title": "Bispecific Antibodies Targeting VEGF and Ang-2",
                "assignee": "Roche/Genentech",
                "filing_date": now - timedelta(days=1800),
                "grant_date": now - timedelta(days=900),
                "expiry_date": now + timedelta(days=3600),
                "status": PatentStatus.GRANTED,
                "therapeutic_area": "Ophthalmology",
                "claims_summary": "Methods and compositions for bispecific antibodies binding VEGF-A and Ang-2 for treating ocular diseases.",
                "relevance_to_portfolio": "Defines freedom-to-operate boundary for EYLEA HD combination approaches.",
                "freedom_to_operate": True,
                "reviewed_by": "IP Counsel - Ophthalmology",
            },
            {
                "id": "PAT-002",
                "patent_number": "US10,987,654",
                "title": "IL-13 Antibody Formulations for Dermatological Conditions",
                "assignee": "Eli Lilly",
                "filing_date": now - timedelta(days=2000),
                "grant_date": now - timedelta(days=1000),
                "expiry_date": now + timedelta(days=3200),
                "status": PatentStatus.GRANTED,
                "therapeutic_area": "Dermatology/Immunology",
                "claims_summary": "Pharmaceutical formulations comprising anti-IL-13 antibodies for subcutaneous administration in atopic dermatitis.",
                "relevance_to_portfolio": "Does not overlap with Dupixent IL-4R alpha mechanism. No FTO concerns.",
                "freedom_to_operate": True,
                "reviewed_by": "IP Counsel - Immunology",
            },
            {
                "id": "PAT-003",
                "patent_number": "WO2024/112233",
                "title": "Extended-Release Anti-VEGF Ocular Implant",
                "assignee": "Kodiak Sciences",
                "filing_date": now - timedelta(days=300),
                "grant_date": None,
                "expiry_date": None,
                "status": PatentStatus.FILED,
                "therapeutic_area": "Ophthalmology",
                "claims_summary": "Sustained-release intravitreal implant with anti-VEGF antibody-biopolymer conjugate for 6-month dosing.",
                "relevance_to_portfolio": "Novel delivery technology. Monitor for potential blocking claims on extended-release approaches.",
                "freedom_to_operate": None,
                "reviewed_by": None,
            },
            {
                "id": "PAT-004",
                "patent_number": "EP3,876,543",
                "title": "Anti-PD-1 Combination Therapy for Cutaneous Squamous Cell Carcinoma",
                "assignee": "Merck",
                "filing_date": now - timedelta(days=1200),
                "grant_date": now - timedelta(days=600),
                "expiry_date": now + timedelta(days=4000),
                "status": PatentStatus.GRANTED,
                "therapeutic_area": "Oncology",
                "claims_summary": "Combination of anti-PD-1 antibody with CTLA-4 antibody for CSCC treatment.",
                "relevance_to_portfolio": "Libtayo has first-mover advantage in CSCC monotherapy. Combination claims may limit future approaches.",
                "freedom_to_operate": True,
                "reviewed_by": "IP Counsel - Oncology",
            },
        ]

        for pat in patents_data:
            self._patents[pat["id"]] = PatentLandscape(**pat)

        # --- Conference Intelligence (4 items) ---
        conference_intel_data = [
            {
                "id": "CI-001",
                "conference_name": "AAO 2025 Annual Meeting",
                "conference_type": ConferenceType.MEDICAL,
                "conference_date": now - timedelta(days=120),
                "location": "Chicago, IL",
                "presentation_title": "Vabysmo 3-Year Durability Data in Wet AMD: TENAYA/LUCERNE Extension",
                "presenter": "Dr. Karl Csaky",
                "company": "Roche/Genentech",
                "therapeutic_area": "Ophthalmology",
                "key_findings": ["87% of patients on q16w or longer intervals at Year 3", "Sustained visual acuity gains", "Favorable safety profile maintained"],
                "competitive_implications": "Strong durability data strengthens Vabysmo positioning. EYLEA HD must emphasize its own long-term data.",
                "threat_level": ThreatLevel.HIGH,
                "attended_by": "Dr. Sarah Mitchell, Medical Affairs",
            },
            {
                "id": "CI-002",
                "conference_name": "EADV 2025 Congress",
                "conference_type": ConferenceType.SCIENTIFIC,
                "conference_date": now - timedelta(days=90),
                "location": "Amsterdam, Netherlands",
                "presentation_title": "Lebrikizumab Long-Term Safety and Efficacy in Atopic Dermatitis: 52-Week Data",
                "presenter": "Dr. Emma Guttman-Yassky",
                "company": "Eli Lilly",
                "therapeutic_area": "Dermatology/Immunology",
                "key_findings": ["Sustained EASI-75 response at 52 weeks", "Monthly dosing convenience", "Comparable safety to placebo"],
                "competitive_implications": "Validates lebrikizumab as durable Dupixent competitor. Monthly dosing advantage for patient compliance.",
                "threat_level": ThreatLevel.MODERATE,
                "attended_by": "Dr. James Park, Immunology Medical Affairs",
            },
            {
                "id": "CI-003",
                "conference_name": "ASCO 2025 Annual Meeting",
                "conference_type": ConferenceType.MEDICAL,
                "conference_date": now - timedelta(days=180),
                "location": "San Francisco, CA",
                "presentation_title": "Keytruda + Padcev Combination in First-Line Urothelial Carcinoma: EV-302 Update",
                "presenter": "Dr. Thomas Powles",
                "company": "Merck/Seagen",
                "therapeutic_area": "Oncology",
                "key_findings": ["Significant OS improvement vs chemotherapy", "PFS benefit maintained", "Manageable safety profile"],
                "competitive_implications": "ADC+IO combination sets new standard of care. Libtayo IO monotherapy positioning unaffected in CSCC but limits expansion into UC.",
                "threat_level": ThreatLevel.LOW,
                "attended_by": "Dr. Rebecca Torres, Oncology Medical Affairs",
            },
            {
                "id": "CI-004",
                "conference_name": "JP Morgan Healthcare Conference 2026",
                "conference_type": ConferenceType.INVESTOR,
                "conference_date": now - timedelta(days=40),
                "location": "San Francisco, CA",
                "presentation_title": "Novartis Pipeline and Strategic Priorities 2026",
                "presenter": "Vas Narasimhan, CEO",
                "company": "Novartis",
                "therapeutic_area": "Ophthalmology",
                "key_findings": ["Beovu repositioned for select patient populations", "New ophthalmology pipeline assets in Phase I", "De-prioritization of retinal franchise"],
                "competitive_implications": "Reduced competitive pressure from Beovu. Novartis shifting resources away from retinal market favors EYLEA HD positioning.",
                "threat_level": ThreatLevel.LOW,
                "attended_by": "Strategic Intelligence Team",
            },
        ]

        for ci in conference_intel_data:
            self._conference_intel[ci["id"]] = ConferenceIntelligence(**ci)

        # --- Competitive Alerts (5 items) ---
        alerts_data = [
            {
                "id": "CA-001",
                "title": "Vabysmo Q4 Revenue Exceeds Expectations",
                "description": "Roche Q4 earnings show Vabysmo annualized revenue surpassing $4B, exceeding consensus estimates by 12%. Share gains accelerating in wet AMD segment.",
                "competitor_name": "Roche/Genentech",
                "therapeutic_area": "Ophthalmology",
                "priority": AlertPriority.URGENT,
                "source": IntelligenceSource.SEC_FILING,
                "created_date": now - timedelta(days=28),
                "acknowledged": True,
                "acknowledged_by": "VP Commercial Strategy",
                "action_taken": "Emergency competitive response meeting scheduled. Updated market access strategy.",
            },
            {
                "id": "CA-002",
                "title": "Lebrikizumab FDA Approval for Atopic Dermatitis",
                "description": "FDA approves Eli Lilly lebrikizumab for moderate-to-severe AD. New biologic competitor entering Dupixent market with monthly dosing advantage.",
                "competitor_name": "Eli Lilly",
                "therapeutic_area": "Dermatology/Immunology",
                "priority": AlertPriority.HIGH,
                "source": IntelligenceSource.FDA_DATABASE,
                "created_date": now - timedelta(days=58),
                "acknowledged": True,
                "acknowledged_by": "Head of Immunology Franchise",
                "action_taken": "Competitive intelligence brief distributed. Medical affairs response plan activated.",
            },
            {
                "id": "CA-003",
                "title": "Keytruda Label Expansion: New Indication in Endometrial Cancer",
                "description": "Merck receives FDA approval for Keytruda in dMMR endometrial cancer, expanding its already broad indication portfolio further.",
                "competitor_name": "Merck",
                "therapeutic_area": "Oncology",
                "priority": AlertPriority.MEDIUM,
                "source": IntelligenceSource.FDA_DATABASE,
                "created_date": now - timedelta(days=15),
                "acknowledged": False,
                "acknowledged_by": None,
                "action_taken": None,
            },
            {
                "id": "CA-004",
                "title": "Kodiak KSI-301 Phase III Data Presentation at Retina Society",
                "description": "Kodiak to present full DAZZLE Phase III dataset at upcoming Retina Society meeting. Potential impact on EYLEA HD competitive narrative.",
                "competitor_name": "Kodiak Sciences",
                "therapeutic_area": "Ophthalmology",
                "priority": AlertPriority.MEDIUM,
                "source": IntelligenceSource.CONFERENCE,
                "created_date": now - timedelta(days=10),
                "acknowledged": False,
                "acknowledged_by": None,
                "action_taken": None,
            },
            {
                "id": "CA-005",
                "title": "AbbVie Rinvoq Head-to-Head Study vs Dupixent Initiated",
                "description": "ClinicalTrials.gov listing shows AbbVie has initiated a head-to-head study comparing Rinvoq to Dupixent in moderate-to-severe AD.",
                "competitor_name": "AbbVie",
                "therapeutic_area": "Dermatology/Immunology",
                "priority": AlertPriority.URGENT,
                "source": IntelligenceSource.CLINICAL_TRIALS_GOV,
                "created_date": now - timedelta(days=5),
                "acknowledged": False,
                "acknowledged_by": None,
                "action_taken": None,
            },
        ]

        for a in alerts_data:
            self._alerts[a["id"]] = CompetitiveAlert(**a)

    # ------------------------------------------------------------------
    # Competitor Programs
    # ------------------------------------------------------------------

    def list_competitor_programs(
        self,
        *,
        therapeutic_area: str | None = None,
        status: CompetitorStatus | None = None,
        threat_level: ThreatLevel | None = None,
    ) -> list[CompetitorProgram]:
        """List competitor programs with optional filters."""
        with self._lock:
            result = list(self._programs.values())

        if therapeutic_area is not None:
            result = [p for p in result if p.therapeutic_area == therapeutic_area]
        if status is not None:
            result = [p for p in result if p.status == status]
        if threat_level is not None:
            result = [p for p in result if p.threat_level == threat_level]

        return sorted(result, key=lambda p: p.id)

    def get_competitor_program(self, program_id: str) -> CompetitorProgram | None:
        """Get a single competitor program by ID."""
        with self._lock:
            return self._programs.get(program_id)

    def create_competitor_program(self, payload: CompetitorProgramCreate) -> CompetitorProgram:
        """Create a new competitor program."""
        now = datetime.now(timezone.utc)
        program_id = f"CP-{uuid4().hex[:8].upper()}"
        program = CompetitorProgram(
            id=program_id,
            competitor_name=payload.competitor_name,
            drug_name=payload.drug_name,
            mechanism_of_action=payload.mechanism_of_action,
            therapeutic_area=payload.therapeutic_area,
            indication=payload.indication,
            status=payload.status,
            threat_level=payload.threat_level,
            our_competing_program=payload.our_competing_program,
            key_differentiators=payload.key_differentiators,
            notes=payload.notes,
            last_updated=now,
            created_at=now,
        )
        with self._lock:
            self._programs[program_id] = program
        logger.info("Created competitor program %s: %s", program_id, payload.drug_name)
        return program

    def update_competitor_program(
        self, program_id: str, payload: CompetitorProgramUpdate
    ) -> CompetitorProgram | None:
        """Update an existing competitor program."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._programs.get(program_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["last_updated"] = now
            updated = CompetitorProgram(**data)
            self._programs[program_id] = updated
        return updated

    def delete_competitor_program(self, program_id: str) -> bool:
        """Delete a competitor program. Returns True if deleted."""
        with self._lock:
            if program_id in self._programs:
                del self._programs[program_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Market Intelligence
    # ------------------------------------------------------------------

    def list_market_intelligence(
        self,
        *,
        source: IntelligenceSource | None = None,
        therapeutic_area: str | None = None,
        threat_level: ThreatLevel | None = None,
    ) -> list[MarketIntelligence]:
        """List market intelligence items with optional filters."""
        with self._lock:
            result = list(self._market_intel.values())

        if source is not None:
            result = [mi for mi in result if mi.source == source]
        if therapeutic_area is not None:
            result = [mi for mi in result if mi.therapeutic_area == therapeutic_area]
        if threat_level is not None:
            result = [mi for mi in result if mi.threat_level == threat_level]

        return sorted(result, key=lambda mi: mi.event_date, reverse=True)

    def get_market_intelligence(self, intel_id: str) -> MarketIntelligence | None:
        """Get a single market intelligence item by ID."""
        with self._lock:
            return self._market_intel.get(intel_id)

    def create_market_intelligence(self, payload: MarketIntelligenceCreate) -> MarketIntelligence:
        """Create a new market intelligence item."""
        now = datetime.now(timezone.utc)
        intel_id = f"MI-{uuid4().hex[:8].upper()}"
        intel = MarketIntelligence(
            id=intel_id,
            source=payload.source,
            title=payload.title,
            summary=payload.summary,
            competitor_name=payload.competitor_name,
            therapeutic_area=payload.therapeutic_area,
            event_date=payload.event_date,
            impact_assessment=payload.impact_assessment,
            threat_level=payload.threat_level,
            source_url=payload.source_url,
            analyzed_by=payload.analyzed_by,
            created_at=now,
        )
        with self._lock:
            self._market_intel[intel_id] = intel
        logger.info("Created market intelligence %s: %s", intel_id, payload.title)
        return intel

    def update_market_intelligence(
        self, intel_id: str, payload: MarketIntelligenceUpdate
    ) -> MarketIntelligence | None:
        """Update an existing market intelligence item."""
        with self._lock:
            existing = self._market_intel.get(intel_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MarketIntelligence(**data)
            self._market_intel[intel_id] = updated
        return updated

    def delete_market_intelligence(self, intel_id: str) -> bool:
        """Delete a market intelligence item. Returns True if deleted."""
        with self._lock:
            if intel_id in self._market_intel:
                del self._market_intel[intel_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Patent Landscape
    # ------------------------------------------------------------------

    def list_patents(
        self,
        *,
        status: PatentStatus | None = None,
        therapeutic_area: str | None = None,
    ) -> list[PatentLandscape]:
        """List patents with optional filters."""
        with self._lock:
            result = list(self._patents.values())

        if status is not None:
            result = [p for p in result if p.status == status]
        if therapeutic_area is not None:
            result = [p for p in result if p.therapeutic_area == therapeutic_area]

        return sorted(result, key=lambda p: p.id)

    def get_patent(self, patent_id: str) -> PatentLandscape | None:
        """Get a single patent by ID."""
        with self._lock:
            return self._patents.get(patent_id)

    def create_patent(self, payload: PatentLandscapeCreate) -> PatentLandscape:
        """Create a new patent record."""
        patent_id = f"PAT-{uuid4().hex[:8].upper()}"
        patent = PatentLandscape(
            id=patent_id,
            patent_number=payload.patent_number,
            title=payload.title,
            assignee=payload.assignee,
            filing_date=payload.filing_date,
            grant_date=payload.grant_date,
            expiry_date=payload.expiry_date,
            status=payload.status,
            therapeutic_area=payload.therapeutic_area,
            claims_summary=payload.claims_summary,
            relevance_to_portfolio=payload.relevance_to_portfolio,
            freedom_to_operate=payload.freedom_to_operate,
            reviewed_by=payload.reviewed_by,
        )
        with self._lock:
            self._patents[patent_id] = patent
        logger.info("Created patent record %s: %s", patent_id, payload.patent_number)
        return patent

    def update_patent(
        self, patent_id: str, payload: PatentLandscapeUpdate
    ) -> PatentLandscape | None:
        """Update an existing patent record."""
        with self._lock:
            existing = self._patents.get(patent_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PatentLandscape(**data)
            self._patents[patent_id] = updated
        return updated

    def delete_patent(self, patent_id: str) -> bool:
        """Delete a patent record. Returns True if deleted."""
        with self._lock:
            if patent_id in self._patents:
                del self._patents[patent_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Conference Intelligence
    # ------------------------------------------------------------------

    def list_conference_intelligence(
        self,
        *,
        conference_type: ConferenceType | None = None,
        therapeutic_area: str | None = None,
        threat_level: ThreatLevel | None = None,
    ) -> list[ConferenceIntelligence]:
        """List conference intelligence items with optional filters."""
        with self._lock:
            result = list(self._conference_intel.values())

        if conference_type is not None:
            result = [ci for ci in result if ci.conference_type == conference_type]
        if therapeutic_area is not None:
            result = [ci for ci in result if ci.therapeutic_area == therapeutic_area]
        if threat_level is not None:
            result = [ci for ci in result if ci.threat_level == threat_level]

        return sorted(result, key=lambda ci: ci.conference_date, reverse=True)

    def get_conference_intelligence(self, intel_id: str) -> ConferenceIntelligence | None:
        """Get a single conference intelligence item by ID."""
        with self._lock:
            return self._conference_intel.get(intel_id)

    def create_conference_intelligence(
        self, payload: ConferenceIntelligenceCreate
    ) -> ConferenceIntelligence:
        """Create a new conference intelligence item."""
        intel_id = f"CI-{uuid4().hex[:8].upper()}"
        intel = ConferenceIntelligence(
            id=intel_id,
            conference_name=payload.conference_name,
            conference_type=payload.conference_type,
            conference_date=payload.conference_date,
            location=payload.location,
            presentation_title=payload.presentation_title,
            presenter=payload.presenter,
            company=payload.company,
            therapeutic_area=payload.therapeutic_area,
            key_findings=payload.key_findings,
            competitive_implications=payload.competitive_implications,
            threat_level=payload.threat_level,
            attended_by=payload.attended_by,
        )
        with self._lock:
            self._conference_intel[intel_id] = intel
        logger.info("Created conference intelligence %s: %s", intel_id, payload.conference_name)
        return intel

    def update_conference_intelligence(
        self, intel_id: str, payload: ConferenceIntelligenceUpdate
    ) -> ConferenceIntelligence | None:
        """Update an existing conference intelligence item."""
        with self._lock:
            existing = self._conference_intel.get(intel_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ConferenceIntelligence(**data)
            self._conference_intel[intel_id] = updated
        return updated

    def delete_conference_intelligence(self, intel_id: str) -> bool:
        """Delete a conference intelligence item. Returns True if deleted."""
        with self._lock:
            if intel_id in self._conference_intel:
                del self._conference_intel[intel_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Competitive Alerts
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        *,
        priority: AlertPriority | None = None,
        acknowledged: bool | None = None,
        therapeutic_area: str | None = None,
    ) -> list[CompetitiveAlert]:
        """List competitive alerts with optional filters."""
        with self._lock:
            result = list(self._alerts.values())

        if priority is not None:
            result = [a for a in result if a.priority == priority]
        if acknowledged is not None:
            result = [a for a in result if a.acknowledged == acknowledged]
        if therapeutic_area is not None:
            result = [a for a in result if a.therapeutic_area == therapeutic_area]

        return sorted(result, key=lambda a: a.created_date, reverse=True)

    def get_alert(self, alert_id: str) -> CompetitiveAlert | None:
        """Get a single alert by ID."""
        with self._lock:
            return self._alerts.get(alert_id)

    def create_alert(self, payload: CompetitiveAlertCreate) -> CompetitiveAlert:
        """Create a new competitive alert."""
        now = datetime.now(timezone.utc)
        alert_id = f"CA-{uuid4().hex[:8].upper()}"
        alert = CompetitiveAlert(
            id=alert_id,
            title=payload.title,
            description=payload.description,
            competitor_name=payload.competitor_name,
            therapeutic_area=payload.therapeutic_area,
            priority=payload.priority,
            source=payload.source,
            created_date=now,
        )
        with self._lock:
            self._alerts[alert_id] = alert
        logger.info("Created competitive alert %s: %s", alert_id, payload.title)
        return alert

    def update_alert(
        self, alert_id: str, payload: CompetitiveAlertUpdate
    ) -> CompetitiveAlert | None:
        """Update an existing competitive alert."""
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CompetitiveAlert(**data)
            self._alerts[alert_id] = updated
        return updated

    def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str
    ) -> CompetitiveAlert | None:
        """Acknowledge a competitive alert."""
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data["acknowledged"] = True
            data["acknowledged_by"] = acknowledged_by
            updated = CompetitiveAlert(**data)
            self._alerts[alert_id] = updated
        logger.info("Acknowledged alert %s by %s", alert_id, acknowledged_by)
        return updated

    def delete_alert(self, alert_id: str) -> bool:
        """Delete a competitive alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CompetitiveIntelligenceMetrics:
        """Compute aggregated competitive intelligence metrics."""
        with self._lock:
            programs = list(self._programs.values())
            market_intel = list(self._market_intel.values())
            patents = list(self._patents.values())
            conference_intel = list(self._conference_intel.values())
            alerts = list(self._alerts.values())

        # Programs by status
        programs_by_status: dict[str, int] = {}
        for p in programs:
            key = p.status.value
            programs_by_status[key] = programs_by_status.get(key, 0) + 1

        # Programs by threat level
        programs_by_threat_level: dict[str, int] = {}
        for p in programs:
            key = p.threat_level.value
            programs_by_threat_level[key] = programs_by_threat_level.get(key, 0) + 1

        # Programs by therapeutic area
        programs_by_therapeutic_area: dict[str, int] = {}
        for p in programs:
            key = p.therapeutic_area
            programs_by_therapeutic_area[key] = programs_by_therapeutic_area.get(key, 0) + 1

        # Intel by source
        intel_by_source: dict[str, int] = {}
        for mi in market_intel:
            key = mi.source.value
            intel_by_source[key] = intel_by_source.get(key, 0) + 1

        # Patents by status
        patents_by_status: dict[str, int] = {}
        for pat in patents:
            key = pat.status.value
            patents_by_status[key] = patents_by_status.get(key, 0) + 1

        # Alerts
        unacknowledged_alerts = sum(1 for a in alerts if not a.acknowledged)
        high_priority_alerts = sum(
            1 for a in alerts if a.priority in (AlertPriority.HIGH, AlertPriority.URGENT)
        )
        critical_threats = sum(
            1 for p in programs if p.threat_level == ThreatLevel.CRITICAL
        )

        return CompetitiveIntelligenceMetrics(
            total_competitor_programs=len(programs),
            programs_by_status=programs_by_status,
            programs_by_threat_level=programs_by_threat_level,
            programs_by_therapeutic_area=programs_by_therapeutic_area,
            total_market_intel=len(market_intel),
            intel_by_source=intel_by_source,
            total_patents=len(patents),
            patents_by_status=patents_by_status,
            total_conference_intel=len(conference_intel),
            total_alerts=len(alerts),
            unacknowledged_alerts=unacknowledged_alerts,
            high_priority_alerts=high_priority_alerts,
            critical_threats=critical_threats,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CompetitiveIntelligenceService | None = None
_instance_lock = threading.Lock()


def get_competitive_intelligence_service() -> CompetitiveIntelligenceService:
    """Return the singleton CompetitiveIntelligenceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CompetitiveIntelligenceService()
    return _instance


def reset_competitive_intelligence_service() -> CompetitiveIntelligenceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CompetitiveIntelligenceService()
    return _instance
