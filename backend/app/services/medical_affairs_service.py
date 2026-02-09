"""Medical Affairs & Publication Planning Service (CLINICAL-12).

Manages publication lifecycle tracking, congress planning, ICMJE compliance
checking, impact factor analysis, author management, and medical affairs metrics.

Usage:
    from app.services.medical_affairs_service import (
        get_medical_affairs_service,
    )

    svc = get_medical_affairs_service()
    pubs = svc.list_publications()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_affairs import (
    AuthorEntry,
    AuthorRole,
    CongressPlan,
    CongressPlanCreate,
    CongressPlanUpdate,
    CongressTier,
    ICMJEComplianceResult,
    JournalImpactTier,
    MedicalAffairsMetrics,
    Publication,
    PublicationCreate,
    PublicationMilestone,
    PublicationPlan,
    PublicationPlanCreate,
    PublicationPlanUpdate,
    PublicationStatus,
    PublicationType,
    PublicationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Impact factor tiers
HIGH_IMPACT_THRESHOLD = 30.0
MID_IMPACT_THRESHOLD = 10.0


class MedicalAffairsService:
    """In-memory Medical Affairs & Publication Planning engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._publications: dict[str, Publication] = {}
        self._congress_plans: dict[str, CongressPlan] = {}
        self._publication_plans: dict[str, PublicationPlan] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic medical affairs data."""
        now = datetime.now(timezone.utc)

        # --- 12 Publications ---
        publications_data = [
            {
                "id": "PUB-001",
                "trial_id": EYLEA_TRIAL,
                "publication_type": PublicationType.PRIMARY_MANUSCRIPT,
                "title": "Efficacy and Safety of Aflibercept 8mg in Neovascular Age-Related Macular Degeneration: Primary Analysis of PULSAR",
                "status": PublicationStatus.PUBLISHED,
                "target_journal": "New England Journal of Medicine",
                "impact_factor": 176.1,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=240),
                "acceptance_date": now - timedelta(days=180),
                "publication_date": now - timedelta(days=150),
                "doi": "10.1056/NEJMoa2301234",
                "authors": [
                    AuthorEntry(name="Dr. Robert Chen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0001-2345-6789", contributions=["Conception and design", "Data acquisition", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Sarah Williams", affiliation="Bascom Palmer Eye Institute", role=AuthorRole.CONTRIBUTING, orcid="0000-0002-3456-7890", contributions=["Data acquisition", "Critical revision"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Michael Torres", affiliation="Wills Eye Hospital", role=AuthorRole.CONTRIBUTING, orcid="0000-0003-4567-8901", contributions=["Data analysis", "Critical revision"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Patricia Nguyen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0004-5678-9012", contributions=["Conception and design", "Final approval"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. James Anderson", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.CORRESPONDING, orcid="0000-0005-6789-0123", contributions=["Study supervision", "Final approval"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-002",
                "trial_id": EYLEA_TRIAL,
                "publication_type": PublicationType.SECONDARY_ANALYSIS,
                "title": "Visual Acuity Outcomes by Baseline Characteristics in PULSAR: A Prespecified Subgroup Analysis",
                "status": PublicationStatus.UNDER_REVIEW,
                "target_journal": "JAMA Ophthalmology",
                "impact_factor": 13.8,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=45),
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Sarah Williams", affiliation="Bascom Palmer Eye Institute", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0002-3456-7890", contributions=["Data analysis", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Robert Chen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0001-2345-6789", contributions=["Conception and design", "Critical revision"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-003",
                "trial_id": EYLEA_TRIAL,
                "publication_type": PublicationType.POST_HOC,
                "title": "Post Hoc Analysis of Retinal Fluid Dynamics in Extended Dosing Intervals with Aflibercept 8mg",
                "status": PublicationStatus.DRAFTING,
                "target_journal": "Retina",
                "impact_factor": 4.6,
                "congress_name": None,
                "congress_date": None,
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Michael Torres", affiliation="Wills Eye Hospital", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0003-4567-8901", contributions=["Data analysis", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Emily Zhang", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.MEDICAL_WRITER, orcid=None, contributions=["Medical writing support"], conflicts_disclosed=True),
                ],
                "icmje_compliant": False,
            },
            {
                "id": "PUB-004",
                "trial_id": DUPIXENT_TRIAL,
                "publication_type": PublicationType.PRIMARY_MANUSCRIPT,
                "title": "Dupilumab in Moderate-to-Severe Atopic Dermatitis: 52-Week Results from LIBERTY AD CHRONOS",
                "status": PublicationStatus.PUBLISHED,
                "target_journal": "The Lancet",
                "impact_factor": 168.9,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=300),
                "acceptance_date": now - timedelta(days=210),
                "publication_date": now - timedelta(days=180),
                "doi": "10.1016/S0140-6736(24)02345-6",
                "authors": [
                    AuthorEntry(name="Dr. Emma Richardson", affiliation="Mount Sinai Hospital", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0006-7890-1234", contributions=["Conception and design", "Data acquisition", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. David Kim", affiliation="Northwestern University", role=AuthorRole.CONTRIBUTING, orcid="0000-0007-8901-2345", contributions=["Data acquisition", "Critical revision"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Lisa Martinez", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.CORRESPONDING, orcid="0000-0008-9012-3456", contributions=["Study supervision", "Final approval"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Thomas Wright", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0009-0123-4567", contributions=["Conception and design", "Final approval"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-005",
                "trial_id": DUPIXENT_TRIAL,
                "publication_type": PublicationType.SECONDARY_ANALYSIS,
                "title": "Impact of Dupilumab on Quality of Life Endpoints: DLQI and POEM Analysis from CHRONOS",
                "status": PublicationStatus.ACCEPTED,
                "target_journal": "Journal of the American Academy of Dermatology",
                "impact_factor": 12.8,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=120),
                "acceptance_date": now - timedelta(days=30),
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. David Kim", affiliation="Northwestern University", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0007-8901-2345", contributions=["Data analysis", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Emma Richardson", affiliation="Mount Sinai Hospital", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0006-7890-1234", contributions=["Conception and design", "Critical revision"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-006",
                "trial_id": LIBTAYO_TRIAL,
                "publication_type": PublicationType.PRIMARY_MANUSCRIPT,
                "title": "Cemiplimab plus Chemotherapy vs Chemotherapy Alone in Non-Small Cell Lung Cancer: EMPOWER-Lung 3",
                "status": PublicationStatus.JOURNAL_SUBMITTED,
                "target_journal": "Journal of Clinical Oncology",
                "impact_factor": 45.3,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=21),
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Alexander Petrov", affiliation="Memorial Sloan Kettering", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0010-1234-5678", contributions=["Conception and design", "Data acquisition", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Jennifer Walsh", affiliation="Dana-Farber Cancer Institute", role=AuthorRole.CONTRIBUTING, orcid="0000-0011-2345-6789", contributions=["Data acquisition", "Critical revision"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Omar Hasan", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.CORRESPONDING, orcid="0000-0012-3456-7890", contributions=["Study supervision", "Final approval"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Patricia Nguyen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0004-5678-9012", contributions=["Conception and design", "Final approval"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-007",
                "trial_id": EYLEA_TRIAL,
                "publication_type": PublicationType.POSTER,
                "title": "Anatomical Outcomes with Aflibercept 8mg: Optical Coherence Tomography Analysis from PULSAR",
                "status": PublicationStatus.PUBLISHED,
                "target_journal": None,
                "impact_factor": None,
                "congress_name": "American Academy of Ophthalmology (AAO) 2025",
                "congress_date": now - timedelta(days=90),
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": now - timedelta(days=90),
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Michael Torres", affiliation="Wills Eye Hospital", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0003-4567-8901", contributions=["Data analysis", "Poster preparation"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Robert Chen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0001-2345-6789", contributions=["Critical revision"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-008",
                "trial_id": DUPIXENT_TRIAL,
                "publication_type": PublicationType.ORAL_PRESENTATION,
                "title": "Long-term Safety Profile of Dupilumab in Atopic Dermatitis: Integrated Analysis of 5 Clinical Trials",
                "status": PublicationStatus.PUBLISHED,
                "target_journal": None,
                "impact_factor": None,
                "congress_name": "American Academy of Dermatology (AAD) 2025",
                "congress_date": now - timedelta(days=60),
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": now - timedelta(days=60),
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Emma Richardson", affiliation="Mount Sinai Hospital", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0006-7890-1234", contributions=["Data analysis", "Presentation preparation"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-009",
                "trial_id": LIBTAYO_TRIAL,
                "publication_type": PublicationType.ABSTRACT,
                "title": "Updated Overall Survival with Cemiplimab Monotherapy in Advanced CSCC: 3-Year Follow-Up",
                "status": PublicationStatus.PUBLISHED,
                "target_journal": None,
                "impact_factor": None,
                "congress_name": "American Society of Clinical Oncology (ASCO) 2025",
                "congress_date": now - timedelta(days=120),
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": now - timedelta(days=120),
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Alexander Petrov", affiliation="Memorial Sloan Kettering", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0010-1234-5678", contributions=["Data analysis", "Abstract preparation"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Omar Hasan", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.CORRESPONDING, orcid="0000-0012-3456-7890", contributions=["Study supervision"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-010",
                "trial_id": LIBTAYO_TRIAL,
                "publication_type": PublicationType.POSTER,
                "title": "Biomarker Analysis of PD-L1 Expression and Tumor Mutational Burden in EMPOWER-Lung 3",
                "status": PublicationStatus.INTERNAL_REVIEW,
                "target_journal": None,
                "impact_factor": None,
                "congress_name": "American Association for Cancer Research (AACR) 2026",
                "congress_date": now + timedelta(days=60),
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Jennifer Walsh", affiliation="Dana-Farber Cancer Institute", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0011-2345-6789", contributions=["Data analysis", "Poster preparation"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Alexander Petrov", affiliation="Memorial Sloan Kettering", role=AuthorRole.SENIOR_AUTHOR, orcid="0000-0010-1234-5678", contributions=["Critical revision"], conflicts_disclosed=True),
                ],
                "icmje_compliant": True,
            },
            {
                "id": "PUB-011",
                "trial_id": DUPIXENT_TRIAL,
                "publication_type": PublicationType.POST_HOC,
                "title": "Dupilumab Effect on Pruritus NRS by Disease Severity: Post Hoc Analysis of CHRONOS",
                "status": PublicationStatus.REVISION_REQUESTED,
                "target_journal": "Journal of the American Academy of Dermatology",
                "impact_factor": 12.8,
                "congress_name": None,
                "congress_date": None,
                "submission_date": now - timedelta(days=90),
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. David Kim", affiliation="Northwestern University", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0007-8901-2345", contributions=["Data analysis", "Drafting the manuscript"], conflicts_disclosed=True),
                    AuthorEntry(name="Dr. Lisa Martinez", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.CORRESPONDING, orcid="0000-0008-9012-3456", contributions=["Study supervision"], conflicts_disclosed=False),
                ],
                "icmje_compliant": False,
            },
            {
                "id": "PUB-012",
                "trial_id": EYLEA_TRIAL,
                "publication_type": PublicationType.REVIEW_ARTICLE,
                "title": "Anti-VEGF Therapy in Retinal Diseases: Current Evidence and Future Directions",
                "status": PublicationStatus.PLANNED,
                "target_journal": "Progress in Retinal and Eye Research",
                "impact_factor": 18.6,
                "congress_name": None,
                "congress_date": None,
                "submission_date": None,
                "acceptance_date": None,
                "publication_date": None,
                "doi": None,
                "authors": [
                    AuthorEntry(name="Dr. Robert Chen", affiliation="Regeneron Pharmaceuticals", role=AuthorRole.FIRST_AUTHOR, orcid="0000-0001-2345-6789", contributions=["Literature review", "Drafting the manuscript"], conflicts_disclosed=True),
                ],
                "icmje_compliant": False,
            },
        ]

        for p in publications_data:
            self._publications[p["id"]] = Publication(**p)

        # --- 5 Congress Plans ---
        congress_data = [
            {
                "id": "CONG-001",
                "congress_name": "American Society of Clinical Oncology (ASCO) 2025",
                "tier": CongressTier.TIER1,
                "date": now - timedelta(days=120),
                "location": "Chicago, IL, USA",
                "abstracts_submitted": 5,
                "abstracts_accepted": 4,
                "posters": 2,
                "orals": 2,
                "booth_reserved": True,
                "budget": 450000.0,
            },
            {
                "id": "CONG-002",
                "congress_name": "American Academy of Dermatology (AAD) 2025",
                "tier": CongressTier.TIER1,
                "date": now - timedelta(days=60),
                "location": "San Francisco, CA, USA",
                "abstracts_submitted": 4,
                "abstracts_accepted": 3,
                "posters": 1,
                "orals": 2,
                "booth_reserved": True,
                "budget": 380000.0,
            },
            {
                "id": "CONG-003",
                "congress_name": "American Association for Cancer Research (AACR) 2026",
                "tier": CongressTier.TIER1,
                "date": now + timedelta(days=60),
                "location": "Orlando, FL, USA",
                "abstracts_submitted": 3,
                "abstracts_accepted": 0,
                "posters": 0,
                "orals": 0,
                "booth_reserved": True,
                "budget": 420000.0,
            },
            {
                "id": "CONG-004",
                "congress_name": "American Academy of Ophthalmology (AAO) 2025",
                "tier": CongressTier.TIER1,
                "date": now - timedelta(days=90),
                "location": "Las Vegas, NV, USA",
                "abstracts_submitted": 6,
                "abstracts_accepted": 5,
                "posters": 3,
                "orals": 2,
                "booth_reserved": True,
                "budget": 400000.0,
            },
            {
                "id": "CONG-005",
                "congress_name": "European Academy of Dermatology and Venereology (EADV) 2025",
                "tier": CongressTier.TIER2,
                "date": now - timedelta(days=45),
                "location": "Amsterdam, Netherlands",
                "abstracts_submitted": 3,
                "abstracts_accepted": 2,
                "posters": 2,
                "orals": 0,
                "booth_reserved": False,
                "budget": 180000.0,
            },
        ]

        for c in congress_data:
            self._congress_plans[c["id"]] = CongressPlan(**c)

        # --- 3 Publication Plans ---
        plans_data = [
            {
                "id": "PPLAN-001",
                "trial_id": EYLEA_TRIAL,
                "planned_publications": ["PUB-001", "PUB-002", "PUB-003", "PUB-007", "PUB-012"],
                "timeline": "Primary manuscript published Q3 2025; secondary analyses Q1-Q2 2026; post-hoc analyses through 2026",
                "milestones": [
                    PublicationMilestone(name="Primary manuscript submission", target_date=now - timedelta(days=240), completed=True),
                    PublicationMilestone(name="Primary manuscript publication", target_date=now - timedelta(days=150), completed=True),
                    PublicationMilestone(name="AAO poster presentation", target_date=now - timedelta(days=90), completed=True),
                    PublicationMilestone(name="Secondary analysis submission", target_date=now - timedelta(days=45), completed=True),
                    PublicationMilestone(name="Post-hoc analysis draft", target_date=now + timedelta(days=30), completed=False),
                    PublicationMilestone(name="Review article submission", target_date=now + timedelta(days=90), completed=False),
                ],
            },
            {
                "id": "PPLAN-002",
                "trial_id": DUPIXENT_TRIAL,
                "planned_publications": ["PUB-004", "PUB-005", "PUB-008", "PUB-011"],
                "timeline": "Primary manuscript published Q2 2025; QoL analysis accepted Q4 2025; oral at AAD 2025; post-hoc in revision",
                "milestones": [
                    PublicationMilestone(name="Primary manuscript submission", target_date=now - timedelta(days=300), completed=True),
                    PublicationMilestone(name="Primary manuscript publication", target_date=now - timedelta(days=180), completed=True),
                    PublicationMilestone(name="AAD oral presentation", target_date=now - timedelta(days=60), completed=True),
                    PublicationMilestone(name="QoL analysis acceptance", target_date=now - timedelta(days=30), completed=True),
                    PublicationMilestone(name="Post-hoc revision resubmission", target_date=now + timedelta(days=14), completed=False),
                ],
            },
            {
                "id": "PPLAN-003",
                "trial_id": LIBTAYO_TRIAL,
                "planned_publications": ["PUB-006", "PUB-009", "PUB-010"],
                "timeline": "ASCO abstract presented Q3 2025; primary manuscript submitted Q4 2025; AACR poster planned Q1 2026",
                "milestones": [
                    PublicationMilestone(name="ASCO abstract presentation", target_date=now - timedelta(days=120), completed=True),
                    PublicationMilestone(name="Primary manuscript submission", target_date=now - timedelta(days=21), completed=True),
                    PublicationMilestone(name="AACR poster submission", target_date=now + timedelta(days=30), completed=False),
                    PublicationMilestone(name="Primary manuscript acceptance", target_date=now + timedelta(days=90), completed=False),
                ],
            },
        ]

        for p in plans_data:
            self._publication_plans[p["id"]] = PublicationPlan(**p)

    # ------------------------------------------------------------------
    # Publication Management
    # ------------------------------------------------------------------

    def list_publications(
        self,
        *,
        trial_id: str | None = None,
        status: PublicationStatus | None = None,
        publication_type: PublicationType | None = None,
    ) -> list[Publication]:
        """List publications with optional filters."""
        with self._lock:
            result = list(self._publications.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]
        if publication_type is not None:
            result = [p for p in result if p.publication_type == publication_type]

        return sorted(result, key=lambda p: p.id)

    def get_publication(self, pub_id: str) -> Publication | None:
        """Get a single publication by ID."""
        with self._lock:
            return self._publications.get(pub_id)

    def create_publication(self, payload: PublicationCreate) -> Publication:
        """Create a new publication."""
        pub_id = f"PUB-{uuid4().hex[:8].upper()}"
        pub = Publication(
            id=pub_id,
            trial_id=payload.trial_id,
            publication_type=payload.publication_type,
            title=payload.title,
            status=PublicationStatus.PLANNED,
            target_journal=payload.target_journal,
            impact_factor=payload.impact_factor,
            congress_name=payload.congress_name,
            congress_date=payload.congress_date,
            submission_date=None,
            acceptance_date=None,
            publication_date=None,
            doi=None,
            authors=payload.authors,
            icmje_compliant=False,
        )
        with self._lock:
            self._publications[pub_id] = pub
        logger.info("Created publication %s: %s", pub_id, payload.title)
        return pub

    def update_publication(self, pub_id: str, payload: PublicationUpdate) -> Publication | None:
        """Update an existing publication."""
        with self._lock:
            existing = self._publications.get(pub_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = Publication(**data)
            self._publications[pub_id] = updated
        return updated

    def delete_publication(self, pub_id: str) -> bool:
        """Delete a publication. Returns True if deleted, False if not found."""
        with self._lock:
            if pub_id in self._publications:
                del self._publications[pub_id]
                return True
            return False

    def advance_publication_status(self, pub_id: str, new_status: PublicationStatus) -> Publication | None:
        """Advance a publication through its lifecycle.

        Automatically sets relevant dates based on status transitions.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._publications.get(pub_id)
            if existing is None:
                return None

            data = existing.model_dump()
            data["status"] = new_status

            # Auto-set dates based on status
            if new_status == PublicationStatus.JOURNAL_SUBMITTED and existing.submission_date is None:
                data["submission_date"] = now
            elif new_status == PublicationStatus.ACCEPTED and existing.acceptance_date is None:
                data["acceptance_date"] = now
            elif new_status == PublicationStatus.PUBLISHED and existing.publication_date is None:
                data["publication_date"] = now

            updated = Publication(**data)
            self._publications[pub_id] = updated

        logger.info("Publication %s status changed to %s", pub_id, new_status.value)
        return updated

    # ------------------------------------------------------------------
    # ICMJE Compliance
    # ------------------------------------------------------------------

    def check_icmje_compliance(self, pub_id: str) -> ICMJEComplianceResult | None:
        """Check ICMJE compliance for a publication.

        ICMJE criteria:
        - All authors must have conflicts_disclosed = True
        - All authors must have at least one documented contribution
        - At least one author must be first_author
        - At least one author must be senior_author or corresponding
        """
        with self._lock:
            pub = self._publications.get(pub_id)
            if pub is None:
                return None

        issues: list[str] = []

        if not pub.authors:
            issues.append("No authors listed")
        else:
            # Check conflicts disclosed
            undisclosed = [a.name for a in pub.authors if not a.conflicts_disclosed]
            if undisclosed:
                issues.append(f"Authors without conflict disclosure: {', '.join(undisclosed)}")

            # Check contributions
            no_contributions = [a.name for a in pub.authors if not a.contributions]
            if no_contributions:
                issues.append(f"Authors without documented contributions: {', '.join(no_contributions)}")

            # Check required roles
            roles = {a.role for a in pub.authors}
            if AuthorRole.FIRST_AUTHOR not in roles:
                issues.append("No first author designated")
            if AuthorRole.SENIOR_AUTHOR not in roles and AuthorRole.CORRESPONDING not in roles:
                issues.append("No senior or corresponding author designated")

        compliant = len(issues) == 0

        # Update publication ICMJE status
        with self._lock:
            existing = self._publications.get(pub_id)
            if existing is not None:
                data = existing.model_dump()
                data["icmje_compliant"] = compliant
                self._publications[pub_id] = Publication(**data)

        return ICMJEComplianceResult(
            publication_id=pub_id,
            compliant=compliant,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Congress Plans
    # ------------------------------------------------------------------

    def list_congress_plans(
        self,
        *,
        tier: CongressTier | None = None,
    ) -> list[CongressPlan]:
        """List congress plans with optional tier filter."""
        with self._lock:
            result = list(self._congress_plans.values())

        if tier is not None:
            result = [c for c in result if c.tier == tier]

        return sorted(result, key=lambda c: c.date, reverse=True)

    def get_congress_plan(self, congress_id: str) -> CongressPlan | None:
        """Get a single congress plan by ID."""
        with self._lock:
            return self._congress_plans.get(congress_id)

    def create_congress_plan(self, payload: CongressPlanCreate) -> CongressPlan:
        """Create a new congress plan."""
        cong_id = f"CONG-{uuid4().hex[:8].upper()}"
        plan = CongressPlan(
            id=cong_id,
            congress_name=payload.congress_name,
            tier=payload.tier,
            date=payload.date,
            location=payload.location,
            abstracts_submitted=0,
            abstracts_accepted=0,
            posters=0,
            orals=0,
            booth_reserved=payload.booth_reserved,
            budget=payload.budget,
        )
        with self._lock:
            self._congress_plans[cong_id] = plan
        logger.info("Created congress plan %s: %s", cong_id, payload.congress_name)
        return plan

    def update_congress_plan(self, congress_id: str, payload: CongressPlanUpdate) -> CongressPlan | None:
        """Update a congress plan."""
        with self._lock:
            existing = self._congress_plans.get(congress_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CongressPlan(**data)
            self._congress_plans[congress_id] = updated
        return updated

    def delete_congress_plan(self, congress_id: str) -> bool:
        """Delete a congress plan. Returns True if deleted."""
        with self._lock:
            if congress_id in self._congress_plans:
                del self._congress_plans[congress_id]
                return True
            return False

    def get_congress_roi(self, congress_id: str) -> dict | None:
        """Calculate ROI metrics for a specific congress.

        Returns acceptance rate, presentations per dollar, etc.
        """
        with self._lock:
            plan = self._congress_plans.get(congress_id)
            if plan is None:
                return None

        acceptance_rate = (
            (plan.abstracts_accepted / plan.abstracts_submitted * 100.0)
            if plan.abstracts_submitted > 0
            else 0.0
        )
        total_presentations = plan.posters + plan.orals
        cost_per_presentation = (
            plan.budget / total_presentations if total_presentations > 0 else 0.0
        )

        return {
            "congress_id": congress_id,
            "congress_name": plan.congress_name,
            "acceptance_rate": round(acceptance_rate, 1),
            "total_presentations": total_presentations,
            "cost_per_presentation": round(cost_per_presentation, 2),
            "abstracts_submitted": plan.abstracts_submitted,
            "abstracts_accepted": plan.abstracts_accepted,
            "budget": plan.budget,
        }

    # ------------------------------------------------------------------
    # Publication Plans
    # ------------------------------------------------------------------

    def list_publication_plans(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[PublicationPlan]:
        """List publication plans with optional trial filter."""
        with self._lock:
            result = list(self._publication_plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]

        return sorted(result, key=lambda p: p.id)

    def get_publication_plan(self, plan_id: str) -> PublicationPlan | None:
        """Get a single publication plan by ID."""
        with self._lock:
            return self._publication_plans.get(plan_id)

    def create_publication_plan(self, payload: PublicationPlanCreate) -> PublicationPlan:
        """Create a new publication plan."""
        plan_id = f"PPLAN-{uuid4().hex[:8].upper()}"
        plan = PublicationPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            planned_publications=payload.planned_publications,
            timeline=payload.timeline,
            milestones=payload.milestones,
        )
        with self._lock:
            self._publication_plans[plan_id] = plan
        logger.info("Created publication plan %s for trial %s", plan_id, payload.trial_id)
        return plan

    def update_publication_plan(self, plan_id: str, payload: PublicationPlanUpdate) -> PublicationPlan | None:
        """Update a publication plan."""
        with self._lock:
            existing = self._publication_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PublicationPlan(**data)
            self._publication_plans[plan_id] = updated
        return updated

    def delete_publication_plan(self, plan_id: str) -> bool:
        """Delete a publication plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._publication_plans:
                del self._publication_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Impact Factor Analysis
    # ------------------------------------------------------------------

    def get_impact_factor_weighted_count(self) -> float:
        """Calculate impact-factor-weighted publication count.

        Only counts published or accepted publications with a known impact factor.
        """
        with self._lock:
            pubs = list(self._publications.values())

        total = 0.0
        for pub in pubs:
            if pub.status in (PublicationStatus.PUBLISHED, PublicationStatus.ACCEPTED):
                if pub.impact_factor is not None and pub.impact_factor > 0:
                    total += pub.impact_factor
        return round(total, 1)

    def classify_journal_tier(self, impact_factor: float) -> JournalImpactTier:
        """Classify a journal's impact tier based on its impact factor."""
        if impact_factor >= HIGH_IMPACT_THRESHOLD:
            return JournalImpactTier.HIGH_IMPACT
        elif impact_factor >= MID_IMPACT_THRESHOLD:
            return JournalImpactTier.MID_IMPACT
        else:
            return JournalImpactTier.SPECIALIZED

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> MedicalAffairsMetrics:
        """Compute aggregated medical affairs metrics."""
        with self._lock:
            pubs = list(self._publications.values())
            congresses = list(self._congress_plans.values())

        # Publications by status
        by_status: dict[str, int] = {}
        for pub in pubs:
            key = pub.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # Publications by type
        by_type: dict[str, int] = {}
        for pub in pubs:
            key = pub.publication_type.value
            by_type[key] = by_type.get(key, 0) + 1

        # Average submission-to-acceptance days
        acceptance_days: list[float] = []
        for pub in pubs:
            if pub.submission_date is not None and pub.acceptance_date is not None:
                delta = (pub.acceptance_date - pub.submission_date).total_seconds() / 86400.0
                acceptance_days.append(delta)

        avg_acceptance = (
            round(sum(acceptance_days) / len(acceptance_days), 1)
            if acceptance_days
            else None
        )

        # Congress ROI (acceptance rate per congress)
        congress_roi: dict[str, float] = {}
        for cong in congresses:
            if cong.abstracts_submitted > 0:
                rate = round(cong.abstracts_accepted / cong.abstracts_submitted * 100.0, 1)
                congress_roi[cong.congress_name] = rate

        # ICMJE compliance rate
        total_pubs = len(pubs)
        compliant_count = sum(1 for p in pubs if p.icmje_compliant)
        icmje_rate = round(compliant_count / max(1, total_pubs) * 100.0, 1)

        # Impact factor weighted count
        if_weighted = self.get_impact_factor_weighted_count()

        return MedicalAffairsMetrics(
            total_publications=total_pubs,
            publications_by_status=by_status,
            publications_by_type=by_type,
            avg_submission_to_acceptance_days=avg_acceptance,
            congress_roi=congress_roi,
            icmje_compliance_rate=icmje_rate,
            impact_factor_weighted_count=if_weighted,
        )

    # ------------------------------------------------------------------
    # Publication Search
    # ------------------------------------------------------------------

    def search_publications(self, query: str) -> list[Publication]:
        """Search publications by title text."""
        q = query.lower()
        with self._lock:
            result = [
                p for p in self._publications.values()
                if q in p.title.lower()
            ]
        return sorted(result, key=lambda p: p.id)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalAffairsService | None = None
_instance_lock = threading.Lock()


def get_medical_affairs_service() -> MedicalAffairsService:
    """Return the singleton MedicalAffairsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalAffairsService()
    return _instance


def reset_medical_affairs_service() -> MedicalAffairsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalAffairsService()
    return _instance
