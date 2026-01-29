"""Clinical Summarization Service.

Generates structured clinical summaries from extracted facts including:
- Section-based summaries (HPI, Assessment, Plan)
- Problem list summarization
- Medication reconciliation summaries
- Discharge summaries
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class SummaryType(Enum):
    """Types of clinical summaries."""

    BRIEF = "brief"  # 1-2 sentence overview
    STANDARD = "standard"  # Paragraph format
    DETAILED = "detailed"  # Full structured summary
    DISCHARGE = "discharge"  # Discharge summary format
    HANDOFF = "handoff"  # Clinical handoff (SBAR)
    PROBLEM_LIST = "problem_list"  # Problem-oriented


class SectionType(Enum):
    """Clinical document section types."""

    CHIEF_COMPLAINT = "chief_complaint"
    HPI = "history_of_present_illness"
    PMH = "past_medical_history"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    SOCIAL_HISTORY = "social_history"
    FAMILY_HISTORY = "family_history"
    REVIEW_OF_SYSTEMS = "review_of_systems"
    PHYSICAL_EXAM = "physical_exam"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    LABS = "laboratory_results"
    IMAGING = "imaging_results"
    PROCEDURES = "procedures"


class ProblemStatus(Enum):
    """Status of clinical problems."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    CHRONIC = "chronic"
    ACUTE = "acute"
    CONTROLLED = "controlled"
    UNCONTROLLED = "uncontrolled"


@dataclass
class ClinicalProblem:
    """A clinical problem with metadata."""

    name: str
    icd10_code: str | None = None
    omop_concept_id: int | None = None
    status: ProblemStatus = ProblemStatus.ACTIVE
    onset_date: str | None = None
    priority: int = 0  # Higher = more important
    associated_medications: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class MedicationEntry:
    """A medication with reconciliation info."""

    name: str
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    indication: str | None = None
    status: str = "active"  # active, discontinued, on-hold, prn
    start_date: str | None = None
    prescriber: str | None = None
    notes: str | None = None


@dataclass
class SectionSummary:
    """Summary of a clinical section."""

    section_type: SectionType
    title: str
    content: str
    bullet_points: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    source_mentions: int = 0


@dataclass
class ClinicalSummary:
    """Complete clinical summary."""

    summary_type: SummaryType
    patient_id: str
    generated_at: str

    # Core summaries
    one_liner: str  # Brief patient description
    sections: list[SectionSummary] = field(default_factory=list)

    # Problem-oriented
    problem_list: list[ClinicalProblem] = field(default_factory=list)
    active_problem_count: int = 0

    # Medications
    medications: list[MedicationEntry] = field(default_factory=list)
    medication_changes: list[str] = field(default_factory=list)

    # Key clinical points
    critical_findings: list[str] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    follow_up_needed: list[str] = field(default_factory=list)

    # Metadata
    source_document_count: int = 0
    total_facts_summarized: int = 0
    confidence_score: float = 0.0


@dataclass
class PatientFact:
    """Input fact for summarization."""

    fact_type: str  # condition, drug, measurement, procedure, observation
    label: str
    value: str | None = None
    unit: str | None = None
    assertion: str = "present"  # present, absent, possible
    temporality: str = "current"  # current, historical, future
    section: str | None = None
    confidence: float = 1.0
    omop_concept_id: int | None = None
    icd10_code: str | None = None


# ============================================================================
# Summarization Templates
# ============================================================================


# SBAR template for handoffs
SBAR_TEMPLATE = """
**SITUATION**
{situation}

**BACKGROUND**
{background}

**ASSESSMENT**
{assessment}

**RECOMMENDATION**
{recommendation}
"""

# Discharge summary template
DISCHARGE_TEMPLATE = """
**DISCHARGE SUMMARY**

**Admission Date:** {admission_date}
**Discharge Date:** {discharge_date}
**Length of Stay:** {los} days

**ADMITTING DIAGNOSIS:**
{admitting_diagnosis}

**DISCHARGE DIAGNOSES:**
{discharge_diagnoses}

**HOSPITAL COURSE:**
{hospital_course}

**DISCHARGE MEDICATIONS:**
{discharge_medications}

**DISCHARGE INSTRUCTIONS:**
{discharge_instructions}

**FOLLOW-UP:**
{follow_up}
"""


# ============================================================================
# Clinical Summarization Service
# ============================================================================


class ClinicalSummarizerService:
    """Service for generating clinical summaries from extracted facts."""

    def __init__(self):
        """Initialize the summarizer service."""
        self._problem_priority = self._build_problem_priority()
        self._section_order = self._build_section_order()

    def _build_problem_priority(self) -> dict[str, int]:
        """Build priority rankings for common conditions."""
        return {
            # Life-threatening - highest priority
            "sepsis": 100,
            "myocardial infarction": 100,
            "stroke": 100,
            "pulmonary embolism": 100,
            "respiratory failure": 95,
            "cardiac arrest": 100,
            "anaphylaxis": 100,

            # Acute serious
            "pneumonia": 80,
            "acute kidney injury": 80,
            "gastrointestinal bleeding": 80,
            "diabetic ketoacidosis": 85,
            "acute pancreatitis": 75,

            # Chronic major
            "heart failure": 70,
            "copd": 65,
            "chronic kidney disease": 65,
            "cirrhosis": 70,
            "cancer": 75,
            "malignancy": 75,

            # Chronic common
            "diabetes mellitus": 50,
            "hypertension": 45,
            "hyperlipidemia": 40,
            "atrial fibrillation": 55,
            "coronary artery disease": 60,

            # Other
            "obesity": 30,
            "gerd": 25,
            "osteoarthritis": 25,
            "depression": 35,
            "anxiety": 30,
        }

    def _build_section_order(self) -> list[SectionType]:
        """Build standard section ordering."""
        return [
            SectionType.CHIEF_COMPLAINT,
            SectionType.HPI,
            SectionType.PMH,
            SectionType.MEDICATIONS,
            SectionType.ALLERGIES,
            SectionType.SOCIAL_HISTORY,
            SectionType.FAMILY_HISTORY,
            SectionType.REVIEW_OF_SYSTEMS,
            SectionType.PHYSICAL_EXAM,
            SectionType.LABS,
            SectionType.IMAGING,
            SectionType.ASSESSMENT,
            SectionType.PLAN,
        ]

    def summarize(
        self,
        patient_id: str,
        facts: list[PatientFact],
        summary_type: SummaryType = SummaryType.STANDARD,
        include_sections: list[SectionType] | None = None,
    ) -> ClinicalSummary:
        """
        Generate a clinical summary from patient facts.

        Args:
            patient_id: Patient identifier
            facts: List of clinical facts to summarize
            summary_type: Type of summary to generate
            include_sections: Specific sections to include (None = all)

        Returns:
            ClinicalSummary with structured content
        """
        # Categorize facts
        conditions = [f for f in facts if f.fact_type == "condition"]
        medications = [f for f in facts if f.fact_type == "drug"]
        measurements = [f for f in facts if f.fact_type == "measurement"]
        procedures = [f for f in facts if f.fact_type == "procedure"]
        observations = [f for f in facts if f.fact_type == "observation"]

        # Build problem list
        problem_list = self._build_problem_list(conditions)

        # Build medication list
        med_list = self._build_medication_list(medications)

        # Generate section summaries
        sections = self._generate_sections(
            facts, problem_list, med_list,
            include_sections or self._section_order
        )

        # Generate one-liner
        one_liner = self._generate_one_liner(
            patient_id, problem_list, med_list, measurements
        )

        # Identify critical findings
        critical = self._identify_critical_findings(facts, measurements)

        # Calculate confidence
        avg_confidence = sum(f.confidence for f in facts) / len(facts) if facts else 0

        return ClinicalSummary(
            summary_type=summary_type,
            patient_id=patient_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            one_liner=one_liner,
            sections=sections,
            problem_list=problem_list,
            active_problem_count=sum(
                1 for p in problem_list
                if p.status in [ProblemStatus.ACTIVE, ProblemStatus.ACUTE, ProblemStatus.UNCONTROLLED]
            ),
            medications=med_list,
            medication_changes=self._identify_med_changes(medications),
            critical_findings=critical,
            pending_items=self._identify_pending_items(facts),
            follow_up_needed=self._identify_follow_up(problem_list, measurements),
            source_document_count=1,
            total_facts_summarized=len(facts),
            confidence_score=round(avg_confidence, 2),
        )

    def _build_problem_list(self, conditions: list[PatientFact]) -> list[ClinicalProblem]:
        """Build prioritized problem list from conditions."""
        problems = []

        for condition in conditions:
            if condition.assertion == "absent":
                continue

            # Determine status
            if condition.temporality == "historical":
                status = ProblemStatus.RESOLVED
            elif "chronic" in condition.label.lower():
                status = ProblemStatus.CHRONIC
            elif "acute" in condition.label.lower():
                status = ProblemStatus.ACUTE
            else:
                status = ProblemStatus.ACTIVE

            # Get priority
            label_lower = condition.label.lower()
            priority = 0
            for term, prio in self._problem_priority.items():
                if term in label_lower:
                    priority = max(priority, prio)

            problems.append(ClinicalProblem(
                name=condition.label,
                icd10_code=condition.icd10_code,
                omop_concept_id=condition.omop_concept_id,
                status=status,
                priority=priority,
            ))

        # Sort by priority descending
        problems.sort(key=lambda p: p.priority, reverse=True)
        return problems

    def _build_medication_list(self, medications: list[PatientFact]) -> list[MedicationEntry]:
        """Build medication list with reconciliation info."""
        meds = []

        for med in medications:
            # Parse dose/frequency from value if present
            dose = None
            frequency = None
            if med.value:
                parts = med.value.split()
                if parts:
                    dose = parts[0]
                    if med.unit:
                        dose += f" {med.unit}"

            status = "active"
            if med.assertion == "absent":
                status = "discontinued"
            elif med.temporality == "historical":
                status = "discontinued"

            meds.append(MedicationEntry(
                name=med.label,
                dose=dose,
                status=status,
            ))

        return meds

    def _generate_sections(
        self,
        facts: list[PatientFact],
        problems: list[ClinicalProblem],
        medications: list[MedicationEntry],
        include_sections: list[SectionType],
    ) -> list[SectionSummary]:
        """Generate section summaries."""
        sections = []

        # Group facts by section
        facts_by_section: dict[str, list[PatientFact]] = {}
        for fact in facts:
            section = fact.section or "unknown"
            if section not in facts_by_section:
                facts_by_section[section] = []
            facts_by_section[section].append(fact)

        for section_type in include_sections:
            if section_type == SectionType.CHIEF_COMPLAINT:
                sections.append(self._summarize_chief_complaint(facts))
            elif section_type == SectionType.HPI:
                sections.append(self._summarize_hpi(facts))
            elif section_type == SectionType.PMH:
                sections.append(self._summarize_pmh(problems))
            elif section_type == SectionType.MEDICATIONS:
                sections.append(self._summarize_medications(medications))
            elif section_type == SectionType.ASSESSMENT:
                sections.append(self._summarize_assessment(problems, facts))
            elif section_type == SectionType.PLAN:
                sections.append(self._summarize_plan(problems, medications))
            elif section_type == SectionType.LABS:
                sections.append(self._summarize_labs(facts))

        return [s for s in sections if s.content]  # Filter empty sections

    def _summarize_chief_complaint(self, facts: list[PatientFact]) -> SectionSummary:
        """Summarize chief complaint section."""
        # Find acute conditions or observations
        acute = [f for f in facts if f.temporality == "current" and f.fact_type in ["condition", "observation"]]

        if not acute:
            return SectionSummary(
                section_type=SectionType.CHIEF_COMPLAINT,
                title="Chief Complaint",
                content="",
            )

        primary = acute[0]
        content = primary.label
        if primary.value:
            content += f" ({primary.value})"

        return SectionSummary(
            section_type=SectionType.CHIEF_COMPLAINT,
            title="Chief Complaint",
            content=content,
            key_findings=[f.label for f in acute[:3]],
            source_mentions=len(acute),
        )

    def _summarize_hpi(self, facts: list[PatientFact]) -> SectionSummary:
        """Summarize history of present illness."""
        current_facts = [f for f in facts if f.temporality == "current"]

        bullets = []
        for fact in current_facts[:10]:
            bullet = fact.label
            if fact.value:
                bullet += f": {fact.value}"
                if fact.unit:
                    bullet += f" {fact.unit}"
            if fact.assertion == "absent":
                bullet = f"No {fact.label}"
            bullets.append(bullet)

        content = ". ".join(bullets) if bullets else ""

        return SectionSummary(
            section_type=SectionType.HPI,
            title="History of Present Illness",
            content=content,
            bullet_points=bullets,
            source_mentions=len(current_facts),
        )

    def _summarize_pmh(self, problems: list[ClinicalProblem]) -> SectionSummary:
        """Summarize past medical history."""
        chronic = [p for p in problems if p.status in [ProblemStatus.CHRONIC, ProblemStatus.RESOLVED]]

        bullets = [p.name for p in chronic]
        content = ", ".join(bullets) if bullets else "No significant past medical history"

        return SectionSummary(
            section_type=SectionType.PMH,
            title="Past Medical History",
            content=content,
            bullet_points=bullets,
            source_mentions=len(chronic),
        )

    def _summarize_medications(self, medications: list[MedicationEntry]) -> SectionSummary:
        """Summarize medications."""
        active_meds = [m for m in medications if m.status == "active"]

        bullets = []
        for med in active_meds:
            entry = med.name
            if med.dose:
                entry += f" {med.dose}"
            if med.frequency:
                entry += f" {med.frequency}"
            bullets.append(entry)

        content = f"{len(active_meds)} active medications" if active_meds else "No current medications"

        return SectionSummary(
            section_type=SectionType.MEDICATIONS,
            title="Medications",
            content=content,
            bullet_points=bullets,
            source_mentions=len(active_meds),
        )

    def _summarize_assessment(
        self,
        problems: list[ClinicalProblem],
        facts: list[PatientFact]
    ) -> SectionSummary:
        """Summarize assessment."""
        active = [p for p in problems if p.status in [ProblemStatus.ACTIVE, ProblemStatus.ACUTE]]

        bullets = []
        for i, problem in enumerate(active[:5], 1):
            bullets.append(f"{i}. {problem.name}")

        content = f"{len(active)} active problems identified"

        return SectionSummary(
            section_type=SectionType.ASSESSMENT,
            title="Assessment",
            content=content,
            bullet_points=bullets,
            key_findings=[p.name for p in active[:3]],
            source_mentions=len(active),
        )

    def _summarize_plan(
        self,
        problems: list[ClinicalProblem],
        medications: list[MedicationEntry]
    ) -> SectionSummary:
        """Summarize plan."""
        bullets = []

        for problem in problems[:5]:
            if problem.status == ProblemStatus.ACTIVE:
                bullets.append(f"Continue management of {problem.name}")
            elif problem.status == ProblemStatus.UNCONTROLLED:
                bullets.append(f"Optimize treatment for {problem.name}")

        content = "Continue current management" if not bullets else f"{len(bullets)} items in plan"

        return SectionSummary(
            section_type=SectionType.PLAN,
            title="Plan",
            content=content,
            bullet_points=bullets,
            source_mentions=len(problems),
        )

    def _summarize_labs(self, facts: list[PatientFact]) -> SectionSummary:
        """Summarize laboratory results."""
        measurements = [f for f in facts if f.fact_type == "measurement"]

        bullets = []
        key_findings = []

        for m in measurements[:10]:
            entry = f"{m.label}: {m.value}"
            if m.unit:
                entry += f" {m.unit}"
            bullets.append(entry)

            # Flag abnormal values
            if m.value:
                try:
                    val = float(m.value)
                    if self._is_critical_value(m.label, val):
                        key_findings.append(f"Critical: {m.label} = {m.value}")
                except ValueError:
                    pass

        content = f"{len(measurements)} lab values" if measurements else "No laboratory results"

        return SectionSummary(
            section_type=SectionType.LABS,
            title="Laboratory Results",
            content=content,
            bullet_points=bullets,
            key_findings=key_findings,
            source_mentions=len(measurements),
        )

    def _generate_one_liner(
        self,
        patient_id: str,
        problems: list[ClinicalProblem],
        medications: list[MedicationEntry],
        measurements: list[PatientFact],
    ) -> str:
        """Generate a one-liner patient summary."""
        # Get top 2-3 problems
        top_problems = [p.name for p in problems[:3]]
        med_count = len([m for m in medications if m.status == "active"])

        if not top_problems:
            return f"Patient {patient_id} with no significant documented conditions"

        problem_str = ", ".join(top_problems)
        return f"Patient with {problem_str}, on {med_count} medications"

    def _identify_critical_findings(
        self,
        facts: list[PatientFact],
        measurements: list[PatientFact]
    ) -> list[str]:
        """Identify critical clinical findings."""
        critical = []

        # Check for critical conditions
        critical_terms = ["sepsis", "arrest", "emergency", "acute", "critical", "severe"]
        for fact in facts:
            if fact.fact_type == "condition":
                for term in critical_terms:
                    if term in fact.label.lower():
                        critical.append(f"Critical condition: {fact.label}")
                        break

        # Check for critical lab values
        for m in measurements:
            if m.value:
                try:
                    val = float(m.value)
                    if self._is_critical_value(m.label, val):
                        critical.append(f"Critical value: {m.label} = {m.value} {m.unit or ''}")
                except ValueError:
                    pass

        return critical[:5]  # Limit to top 5

    def _is_critical_value(self, lab_name: str, value: float) -> bool:
        """Check if a lab value is critical."""
        lab_lower = lab_name.lower()

        critical_ranges = {
            "potassium": (2.5, 6.5),
            "sodium": (120, 160),
            "glucose": (40, 500),
            "creatinine": (0, 10.0),
            "hemoglobin": (5.0, 20.0),
            "platelet": (20, 1000),
            "inr": (0, 5.0),
        }

        for lab, (low, high) in critical_ranges.items():
            if lab in lab_lower:
                return value < low or value > high

        return False

    def _identify_med_changes(self, medications: list[PatientFact]) -> list[str]:
        """Identify medication changes."""
        changes = []

        for med in medications:
            if med.assertion == "absent" or med.temporality == "historical":
                changes.append(f"Discontinued: {med.label}")
            elif "new" in (med.section or "").lower():
                changes.append(f"Started: {med.label}")

        return changes

    def _identify_pending_items(self, facts: list[PatientFact]) -> list[str]:
        """Identify pending clinical items."""
        pending = []

        for fact in facts:
            if fact.temporality == "future":
                pending.append(f"Pending: {fact.label}")
            elif "pending" in fact.label.lower() or "ordered" in fact.label.lower():
                pending.append(fact.label)

        return pending[:5]

    def _identify_follow_up(
        self,
        problems: list[ClinicalProblem],
        measurements: list[PatientFact]
    ) -> list[str]:
        """Identify follow-up needs."""
        follow_up = []

        for problem in problems:
            if problem.status == ProblemStatus.UNCONTROLLED:
                follow_up.append(f"Follow up on {problem.name}")
            elif problem.status == ProblemStatus.ACUTE:
                follow_up.append(f"Close monitoring for {problem.name}")

        return follow_up[:5]

    def generate_sbar(
        self,
        patient_id: str,
        facts: list[PatientFact],
    ) -> str:
        """Generate SBAR handoff summary."""
        summary = self.summarize(patient_id, facts, SummaryType.HANDOFF)

        # Build SBAR components
        situation = summary.one_liner

        # Background
        pmh = [s for s in summary.sections if s.section_type == SectionType.PMH]
        background = pmh[0].content if pmh else "No significant past medical history"

        # Assessment
        assessment_parts = []
        for problem in summary.problem_list[:5]:
            assessment_parts.append(f"- {problem.name} ({problem.status.value})")
        assessment = "\n".join(assessment_parts) if assessment_parts else "Stable"

        # Recommendation
        recommendations = []
        for item in summary.pending_items[:3]:
            recommendations.append(f"- {item}")
        for item in summary.follow_up_needed[:3]:
            recommendations.append(f"- {item}")
        recommendation = "\n".join(recommendations) if recommendations else "Continue current plan"

        return SBAR_TEMPLATE.format(
            situation=situation,
            background=background,
            assessment=assessment,
            recommendation=recommendation,
        )

    def generate_problem_summary(
        self,
        patient_id: str,
        facts: list[PatientFact],
    ) -> dict[str, Any]:
        """Generate problem-oriented summary."""
        summary = self.summarize(patient_id, facts, SummaryType.PROBLEM_LIST)

        problems_by_status: dict[str, list[dict]] = {
            "active": [],
            "chronic": [],
            "resolved": [],
        }

        for problem in summary.problem_list:
            entry = {
                "name": problem.name,
                "icd10": problem.icd10_code,
                "priority": problem.priority,
                "medications": problem.associated_medications,
            }

            if problem.status in [ProblemStatus.ACTIVE, ProblemStatus.ACUTE, ProblemStatus.UNCONTROLLED]:
                problems_by_status["active"].append(entry)
            elif problem.status == ProblemStatus.CHRONIC:
                problems_by_status["chronic"].append(entry)
            else:
                problems_by_status["resolved"].append(entry)

        return {
            "patient_id": patient_id,
            "generated_at": summary.generated_at,
            "total_problems": len(summary.problem_list),
            "problems_by_status": problems_by_status,
            "critical_findings": summary.critical_findings,
            "medication_count": len(summary.medications),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "problem_priorities_tracked": len(self._problem_priority),
            "section_types": len(SectionType),
            "summary_types": len(SummaryType),
            "supported_sections": [s.value for s in self._section_order],
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: ClinicalSummarizerService | None = None
_service_lock = threading.Lock()


def get_clinical_summarizer_service() -> ClinicalSummarizerService:
    """Get or create the singleton service instance."""
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = ClinicalSummarizerService()

    return _service_instance


def reset_clinical_summarizer_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
