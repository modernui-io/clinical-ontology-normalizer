"""CDISC Controlled Terminology Service.

This module provides CDISC Controlled Terminology (CT) services for clinical trials:
- Codelist management with C-codes and submission values
- Support for multiple CT versions (2024-03-29, etc.)
- Extensible vs non-extensible codelist enforcement
- SDTM domain-based codelist lookup
- NCI EVS format parsing support

CDISC CT is the official set of controlled terminologies used in:
- SDTM (Study Data Tabulation Model)
- ADaM (Analysis Data Model)
- CDASH (Clinical Data Acquisition Standards Harmonization)

Common codelists include:
- SEX (C66731), RACE (C74457), ETHNIC (C66790)
- AEOUT (C66768), AEACN (C66767), AESEV (C66769)
- COUNTRY (C66729), ROUTE (C66729)

Note: Full CDISC CT is available from NCI EVS at:
https://evs.nci.nih.gov/ftp1/CDISC/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
from pathlib import Path
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)


class CDISCDomain(Enum):
    """SDTM domains that use controlled terminology."""

    DM = "Demographics"
    AE = "Adverse Events"
    CM = "Concomitant Medications"
    DS = "Disposition"
    DV = "Protocol Deviations"
    EX = "Exposure"
    LB = "Laboratory Test Results"
    MH = "Medical History"
    PE = "Physical Examination"
    SC = "Subject Characteristics"
    SU = "Substance Use"
    VS = "Vital Signs"
    EG = "ECG Test Results"
    IE = "Inclusion/Exclusion Criteria"
    TU = "Tumor Identification"
    TR = "Tumor Response"
    RS = "Disease Response"
    FA = "Findings About"
    GENERAL = "General/Cross-Domain"


class CodelistType(Enum):
    """Type of codelist."""

    EXTENSIBLE = "extensible"  # Allows sponsor-defined terms
    NON_EXTENSIBLE = "non-extensible"  # Must use defined terms only


@dataclass
class CodelistTerm:
    """A term within a CDISC codelist."""

    code: str  # NCI C-code for the term (e.g., C25191)
    codelist_code: str  # Parent codelist C-code
    submission_value: str  # Value used in SDTM submission (e.g., "M")
    preferred_term: str  # Preferred display term (e.g., "Male")
    synonyms: list[str] = field(default_factory=list)
    definition: str = ""
    nci_code: str = ""  # Full NCI code with prefix
    ordinal: int = 0  # Order in codelist
    is_extensible_term: bool = False  # True if sponsor-added term


@dataclass
class Codelist:
    """A CDISC controlled terminology codelist."""

    c_code: str  # NCI C-code (e.g., C66731)
    name: str  # Codelist name (e.g., "Sex")
    submission_value: str  # Short name for submission (e.g., "SEX")
    definition: str = ""
    codelist_type: CodelistType = CodelistType.NON_EXTENSIBLE
    domain: CDISCDomain = CDISCDomain.GENERAL
    terms: list[CodelistTerm] = field(default_factory=list)
    version: str = ""  # CT version
    nci_preferred_term: str = ""
    related_codelists: list[str] = field(default_factory=list)  # Related C-codes


@dataclass
class ValidationResult:
    """Result of validating a term against a codelist."""

    is_valid: bool
    codelist_code: str
    codelist_name: str
    submitted_value: str
    matched_term: CodelistTerm | None = None
    message: str = ""
    is_extensible: bool = False
    suggestions: list[CodelistTerm] = field(default_factory=list)


@dataclass
class CDISCVersion:
    """A CDISC CT release version."""

    version: str  # e.g., "2024-03-29"
    release_date: datetime
    description: str = ""
    codelist_count: int = 0
    term_count: int = 0
    is_current: bool = False


# ============================================================================
# Fixture Path
# ============================================================================

CDISC_FIXTURE_FILE = Path(__file__).parent.parent.parent / "fixtures" / "cdisc_terminology.json"


# ============================================================================
# Singleton Instance
# ============================================================================

_cdisc_service: "CDISCTerminologyService | None" = None
_cdisc_lock = threading.Lock()


def get_cdisc_terminology_service() -> "CDISCTerminologyService":
    """Get the singleton CDISC terminology service instance."""
    global _cdisc_service
    if _cdisc_service is None:
        with _cdisc_lock:
            if _cdisc_service is None:
                _cdisc_service = CDISCTerminologyService()
    return _cdisc_service


def reset_cdisc_terminology_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _cdisc_service
    with _cdisc_lock:
        _cdisc_service = None


# ============================================================================
# CDISC Terminology Service Implementation
# ============================================================================

class CDISCTerminologyService:
    """Service for CDISC Controlled Terminology management.

    Provides:
    - Codelist lookup by C-code
    - Term validation against codelists
    - Domain-based codelist discovery
    - Multi-version support
    - Search across codelists and terms
    """

    def __init__(self) -> None:
        """Initialize the CDISC terminology service."""
        # Primary index: C-code -> Codelist
        self._codelists: dict[str, Codelist] = {}
        # Index by submission value
        self._by_submission_value: dict[str, str] = {}  # submission_value -> c_code
        # Index by domain
        self._by_domain: dict[CDISCDomain, list[str]] = {}  # domain -> list of c_codes
        # Term index for search
        self._term_index: dict[str, list[tuple[str, str]]] = {}  # term_lower -> [(codelist_code, term_code)]
        # Version tracking
        self._versions: dict[str, CDISCVersion] = {}
        self._current_version: str = ""

        self._load_terminology()
        logger.info(
            f"CDISC terminology service initialized with {len(self._codelists)} codelists, "
            f"version {self._current_version}"
        )

    def _load_terminology(self) -> None:
        """Load CDISC terminology from fixture file."""
        if CDISC_FIXTURE_FILE.exists():
            try:
                with open(CDISC_FIXTURE_FILE, "r") as f:
                    data = json.load(f)
                self._parse_terminology_data(data)
                return
            except Exception as e:
                logger.warning(f"Error loading CDISC terminology: {e}")

        # If no fixture, load built-in terminology
        self._load_builtin_terminology()

    def _parse_terminology_data(self, data: dict[str, Any]) -> None:
        """Parse terminology data from JSON."""
        metadata = data.get("metadata", {})
        self._current_version = metadata.get("version", "2024-03-29")

        # Parse versions
        for version_data in data.get("versions", []):
            version = CDISCVersion(
                version=version_data.get("version", ""),
                release_date=datetime.fromisoformat(version_data.get("release_date", "2024-03-29")),
                description=version_data.get("description", ""),
                codelist_count=version_data.get("codelist_count", 0),
                term_count=version_data.get("term_count", 0),
                is_current=version_data.get("is_current", False),
            )
            self._versions[version.version] = version

        # Parse codelists
        for codelist_data in data.get("codelists", []):
            codelist = self._parse_codelist(codelist_data)
            if codelist:
                self._index_codelist(codelist)

    def _parse_codelist(self, data: dict[str, Any]) -> Codelist | None:
        """Parse a codelist from JSON data."""
        c_code = data.get("c_code", "")
        if not c_code:
            return None

        # Determine codelist type
        type_str = data.get("codelist_type", "non-extensible").lower()
        codelist_type = CodelistType.EXTENSIBLE if "extensible" in type_str else CodelistType.NON_EXTENSIBLE

        # Determine domain
        domain_str = data.get("domain", "GENERAL").upper()
        try:
            domain = CDISCDomain[domain_str]
        except KeyError:
            domain = CDISCDomain.GENERAL

        # Parse terms
        terms: list[CodelistTerm] = []
        for idx, term_data in enumerate(data.get("terms", [])):
            term = CodelistTerm(
                code=term_data.get("code", ""),
                codelist_code=c_code,
                submission_value=term_data.get("submission_value", ""),
                preferred_term=term_data.get("preferred_term", ""),
                synonyms=term_data.get("synonyms", []),
                definition=term_data.get("definition", ""),
                nci_code=term_data.get("nci_code", ""),
                ordinal=term_data.get("ordinal", idx),
                is_extensible_term=term_data.get("is_extensible_term", False),
            )
            terms.append(term)

        return Codelist(
            c_code=c_code,
            name=data.get("name", ""),
            submission_value=data.get("submission_value", ""),
            definition=data.get("definition", ""),
            codelist_type=codelist_type,
            domain=domain,
            terms=terms,
            version=data.get("version", self._current_version),
            nci_preferred_term=data.get("nci_preferred_term", ""),
            related_codelists=data.get("related_codelists", []),
        )

    def _index_codelist(self, codelist: Codelist) -> None:
        """Index a codelist for fast lookup."""
        c_code = codelist.c_code
        self._codelists[c_code] = codelist

        # Index by submission value
        if codelist.submission_value:
            self._by_submission_value[codelist.submission_value.upper()] = c_code

        # Index by domain
        if codelist.domain not in self._by_domain:
            self._by_domain[codelist.domain] = []
        self._by_domain[codelist.domain].append(c_code)

        # Index terms for search
        for term in codelist.terms:
            # Index submission value
            sv_lower = term.submission_value.lower()
            if sv_lower not in self._term_index:
                self._term_index[sv_lower] = []
            self._term_index[sv_lower].append((c_code, term.code))

            # Index preferred term
            pt_lower = term.preferred_term.lower()
            if pt_lower not in self._term_index:
                self._term_index[pt_lower] = []
            self._term_index[pt_lower].append((c_code, term.code))

            # Index synonyms
            for synonym in term.synonyms:
                syn_lower = synonym.lower()
                if syn_lower not in self._term_index:
                    self._term_index[syn_lower] = []
                self._term_index[syn_lower].append((c_code, term.code))

    def _load_builtin_terminology(self) -> None:
        """Load built-in CDISC terminology for common codelists."""
        # This provides essential SDTM codelists even without external fixture
        builtin_codelists = self._get_builtin_codelists()
        for codelist_data in builtin_codelists:
            codelist = self._parse_codelist(codelist_data)
            if codelist:
                self._index_codelist(codelist)

        self._current_version = "2024-03-29"
        self._versions[self._current_version] = CDISCVersion(
            version=self._current_version,
            release_date=datetime(2024, 3, 29),
            description="CDISC CT 2024-03-29 (Built-in subset)",
            codelist_count=len(self._codelists),
            term_count=sum(len(cl.terms) for cl in self._codelists.values()),
            is_current=True,
        )

    def _get_builtin_codelists(self) -> list[dict[str, Any]]:
        """Get built-in codelist definitions for common SDTM codelists."""
        return [
            # =================================================================
            # SEX (C66731) - Demographics
            # =================================================================
            {
                "c_code": "C66731",
                "name": "Sex",
                "submission_value": "SEX",
                "definition": "The biological sex of an individual.",
                "codelist_type": "non-extensible",
                "domain": "DM",
                "terms": [
                    {
                        "code": "C16576",
                        "submission_value": "F",
                        "preferred_term": "Female",
                        "definition": "A person who belongs to the sex that normally produces ova.",
                        "synonyms": ["Female", "Woman", "Girl"],
                    },
                    {
                        "code": "C20197",
                        "submission_value": "M",
                        "preferred_term": "Male",
                        "definition": "A person who belongs to the sex that normally produces sperm.",
                        "synonyms": ["Male", "Man", "Boy"],
                    },
                    {
                        "code": "C38046",
                        "submission_value": "U",
                        "preferred_term": "Unknown",
                        "definition": "Not known, not observed, not recorded, or refused.",
                        "synonyms": ["Unknown", "Not Known"],
                    },
                    {
                        "code": "C48660",
                        "submission_value": "UNDIFFERENTIATED",
                        "preferred_term": "Undifferentiated",
                        "definition": "Sex could not be determined; not clear which sex.",
                        "synonyms": ["Undifferentiated", "Intersex"],
                    },
                ],
            },
            # =================================================================
            # RACE (C74457) - Demographics
            # =================================================================
            {
                "c_code": "C74457",
                "name": "Race",
                "submission_value": "RACE",
                "definition": "A categorization of humans based on physical characteristics.",
                "codelist_type": "extensible",
                "domain": "DM",
                "terms": [
                    {
                        "code": "C41259",
                        "submission_value": "AMERICAN INDIAN OR ALASKA NATIVE",
                        "preferred_term": "American Indian or Alaska Native",
                        "definition": "A person having origins in any of the original peoples of North and South America.",
                        "synonyms": ["Native American", "Indigenous"],
                    },
                    {
                        "code": "C41260",
                        "submission_value": "ASIAN",
                        "preferred_term": "Asian",
                        "definition": "A person having origins in any of the original peoples of the Far East, Southeast Asia, or the Indian subcontinent.",
                        "synonyms": ["Asian"],
                    },
                    {
                        "code": "C16352",
                        "submission_value": "BLACK OR AFRICAN AMERICAN",
                        "preferred_term": "Black or African American",
                        "definition": "A person having origins in any of the Black racial groups of Africa.",
                        "synonyms": ["Black", "African American"],
                    },
                    {
                        "code": "C41219",
                        "submission_value": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
                        "preferred_term": "Native Hawaiian or Other Pacific Islander",
                        "definition": "A person having origins in any of the original peoples of Hawaii, Guam, Samoa, or other Pacific Islands.",
                        "synonyms": ["Pacific Islander", "Hawaiian"],
                    },
                    {
                        "code": "C41261",
                        "submission_value": "WHITE",
                        "preferred_term": "White",
                        "definition": "A person having origins in any of the original peoples of Europe, the Middle East, or North Africa.",
                        "synonyms": ["White", "Caucasian"],
                    },
                    {
                        "code": "C17998",
                        "submission_value": "UNKNOWN",
                        "preferred_term": "Unknown",
                        "definition": "Not known, not observed, not recorded, or refused.",
                        "synonyms": ["Unknown", "Not Reported"],
                    },
                    {
                        "code": "C43234",
                        "submission_value": "MULTIPLE",
                        "preferred_term": "Multiple",
                        "definition": "Having more than one race.",
                        "synonyms": ["Multiple", "Mixed Race", "Multiracial"],
                    },
                    {
                        "code": "C66790",
                        "submission_value": "OTHER",
                        "preferred_term": "Other",
                        "definition": "Different from the one(s) specified.",
                        "synonyms": ["Other"],
                    },
                ],
            },
            # =================================================================
            # ETHNIC (C66790) - Demographics
            # =================================================================
            {
                "c_code": "C66790",
                "name": "Ethnicity",
                "submission_value": "ETHNIC",
                "definition": "The ethnic group of an individual.",
                "codelist_type": "non-extensible",
                "domain": "DM",
                "terms": [
                    {
                        "code": "C17459",
                        "submission_value": "HISPANIC OR LATINO",
                        "preferred_term": "Hispanic or Latino",
                        "definition": "A person of Cuban, Mexican, Puerto Rican, South or Central American, or other Spanish culture or origin.",
                        "synonyms": ["Hispanic", "Latino", "Latina", "Latinx"],
                    },
                    {
                        "code": "C41222",
                        "submission_value": "NOT HISPANIC OR LATINO",
                        "preferred_term": "Not Hispanic or Latino",
                        "definition": "A person not of Cuban, Mexican, Puerto Rican, South or Central American, or other Spanish culture or origin.",
                        "synonyms": ["Not Hispanic", "Non-Hispanic"],
                    },
                    {
                        "code": "C17998",
                        "submission_value": "UNKNOWN",
                        "preferred_term": "Unknown",
                        "definition": "Not known, not observed, not recorded, or refused.",
                        "synonyms": ["Unknown", "Not Reported"],
                    },
                    {
                        "code": "C66789",
                        "submission_value": "NOT REPORTED",
                        "preferred_term": "Not Reported",
                        "definition": "Not provided or available.",
                        "synonyms": ["Not Reported"],
                    },
                ],
            },
            # =================================================================
            # COUNTRY (C66729) - Demographics
            # =================================================================
            {
                "c_code": "C66729",
                "name": "Country",
                "submission_value": "COUNTRY",
                "definition": "A set of countries using ISO 3166-1 alpha-3 codes.",
                "codelist_type": "extensible",
                "domain": "DM",
                "terms": [
                    {"code": "C16984", "submission_value": "USA", "preferred_term": "United States of America", "synonyms": ["United States", "US", "America"]},
                    {"code": "C17241", "submission_value": "GBR", "preferred_term": "United Kingdom", "synonyms": ["UK", "Britain", "England"]},
                    {"code": "C16536", "submission_value": "FRA", "preferred_term": "France", "synonyms": ["France"]},
                    {"code": "C16643", "submission_value": "DEU", "preferred_term": "Germany", "synonyms": ["Germany", "Deutschland"]},
                    {"code": "C17087", "submission_value": "ITA", "preferred_term": "Italy", "synonyms": ["Italy", "Italia"]},
                    {"code": "C20317", "submission_value": "ESP", "preferred_term": "Spain", "synonyms": ["Spain", "Espana"]},
                    {"code": "C16408", "submission_value": "CAN", "preferred_term": "Canada", "synonyms": ["Canada"]},
                    {"code": "C16310", "submission_value": "AUS", "preferred_term": "Australia", "synonyms": ["Australia"]},
                    {"code": "C17089", "submission_value": "JPN", "preferred_term": "Japan", "synonyms": ["Japan", "Nippon"]},
                    {"code": "C16441", "submission_value": "CHN", "preferred_term": "China", "synonyms": ["China", "PRC"]},
                    {"code": "C17078", "submission_value": "IND", "preferred_term": "India", "synonyms": ["India"]},
                    {"code": "C16362", "submission_value": "BRA", "preferred_term": "Brazil", "synonyms": ["Brazil", "Brasil"]},
                    {"code": "C17156", "submission_value": "MEX", "preferred_term": "Mexico", "synonyms": ["Mexico"]},
                    {"code": "C17243", "submission_value": "KOR", "preferred_term": "Republic of Korea", "synonyms": ["South Korea", "Korea"]},
                ],
            },
            # =================================================================
            # AEOUT (C66768) - Adverse Event Outcome
            # =================================================================
            {
                "c_code": "C66768",
                "name": "Outcome of Adverse Event",
                "submission_value": "AEOUT",
                "definition": "The final result or outcome of the adverse event.",
                "codelist_type": "non-extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C49494",
                        "submission_value": "RECOVERED/RESOLVED",
                        "preferred_term": "Recovered/Resolved",
                        "definition": "The adverse event has completely resolved.",
                        "synonyms": ["Recovered", "Resolved", "Complete Resolution"],
                    },
                    {
                        "code": "C49495",
                        "submission_value": "RECOVERING/RESOLVING",
                        "preferred_term": "Recovering/Resolving",
                        "definition": "The adverse event is in the process of resolving.",
                        "synonyms": ["Recovering", "Resolving", "Improving"],
                    },
                    {
                        "code": "C49496",
                        "submission_value": "NOT RECOVERED/NOT RESOLVED",
                        "preferred_term": "Not Recovered/Not Resolved",
                        "definition": "The adverse event has not resolved.",
                        "synonyms": ["Not Recovered", "Not Resolved", "Ongoing"],
                    },
                    {
                        "code": "C49497",
                        "submission_value": "RECOVERED/RESOLVED WITH SEQUELAE",
                        "preferred_term": "Recovered/Resolved with Sequelae",
                        "definition": "The adverse event resolved with residual effects.",
                        "synonyms": ["With Sequelae", "Residual Effects"],
                    },
                    {
                        "code": "C48275",
                        "submission_value": "FATAL",
                        "preferred_term": "Fatal",
                        "definition": "The adverse event resulted in death.",
                        "synonyms": ["Fatal", "Death", "Died"],
                    },
                    {
                        "code": "C17998",
                        "submission_value": "UNKNOWN",
                        "preferred_term": "Unknown",
                        "definition": "The outcome is not known.",
                        "synonyms": ["Unknown"],
                    },
                ],
            },
            # =================================================================
            # AEACN (C66767) - Action Taken with Study Treatment
            # =================================================================
            {
                "c_code": "C66767",
                "name": "Action Taken with Study Treatment",
                "submission_value": "AEACN",
                "definition": "The action taken with the study treatment as a result of the adverse event.",
                "codelist_type": "non-extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C49500",
                        "submission_value": "DRUG WITHDRAWN",
                        "preferred_term": "Drug Withdrawn",
                        "definition": "The study drug was permanently discontinued.",
                        "synonyms": ["Withdrawn", "Discontinued", "Stopped"],
                    },
                    {
                        "code": "C49501",
                        "submission_value": "DOSE REDUCED",
                        "preferred_term": "Dose Reduced",
                        "definition": "The dose of the study drug was reduced.",
                        "synonyms": ["Reduced", "Dose Decrease"],
                    },
                    {
                        "code": "C49502",
                        "submission_value": "DOSE INCREASED",
                        "preferred_term": "Dose Increased",
                        "definition": "The dose of the study drug was increased.",
                        "synonyms": ["Increased", "Dose Increase"],
                    },
                    {
                        "code": "C49503",
                        "submission_value": "DOSE NOT CHANGED",
                        "preferred_term": "Dose Not Changed",
                        "definition": "The dose of the study drug was not changed.",
                        "synonyms": ["No Change", "Unchanged"],
                    },
                    {
                        "code": "C49504",
                        "submission_value": "DRUG INTERRUPTED",
                        "preferred_term": "Drug Interrupted",
                        "definition": "The study drug was temporarily interrupted.",
                        "synonyms": ["Interrupted", "Held", "Paused"],
                    },
                    {
                        "code": "C49505",
                        "submission_value": "NOT APPLICABLE",
                        "preferred_term": "Not Applicable",
                        "definition": "Not applicable for this adverse event.",
                        "synonyms": ["N/A", "Not Applicable"],
                    },
                    {
                        "code": "C17998",
                        "submission_value": "UNKNOWN",
                        "preferred_term": "Unknown",
                        "definition": "The action taken is not known.",
                        "synonyms": ["Unknown"],
                    },
                ],
            },
            # =================================================================
            # AESEV (C66769) - Severity/Intensity Scale for Adverse Events
            # =================================================================
            {
                "c_code": "C66769",
                "name": "Severity/Intensity Scale for Adverse Events",
                "submission_value": "AESEV",
                "definition": "The severity or intensity of the adverse event.",
                "codelist_type": "non-extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C41338",
                        "submission_value": "MILD",
                        "preferred_term": "Mild",
                        "definition": "Awareness of symptoms but easily tolerated.",
                        "synonyms": ["Mild", "Grade 1"],
                        "ordinal": 1,
                    },
                    {
                        "code": "C41339",
                        "submission_value": "MODERATE",
                        "preferred_term": "Moderate",
                        "definition": "Discomfort enough to cause interference with usual activity.",
                        "synonyms": ["Moderate", "Grade 2"],
                        "ordinal": 2,
                    },
                    {
                        "code": "C41340",
                        "submission_value": "SEVERE",
                        "preferred_term": "Severe",
                        "definition": "Incapacitating with inability to work or do usual activity.",
                        "synonyms": ["Severe", "Grade 3"],
                        "ordinal": 3,
                    },
                ],
            },
            # =================================================================
            # AETOXGR (C66781) - NCI CTCAE Grade Scale for Adverse Events
            # =================================================================
            {
                "c_code": "C66781",
                "name": "NCI CTCAE Grade Scale for Adverse Events",
                "submission_value": "AETOXGR",
                "definition": "NCI Common Terminology Criteria for Adverse Events grading scale.",
                "codelist_type": "non-extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C41338",
                        "submission_value": "1",
                        "preferred_term": "Grade 1",
                        "definition": "Mild; asymptomatic or mild symptoms; clinical or diagnostic observations only.",
                        "synonyms": ["Grade 1", "Mild"],
                        "ordinal": 1,
                    },
                    {
                        "code": "C41339",
                        "submission_value": "2",
                        "preferred_term": "Grade 2",
                        "definition": "Moderate; minimal, local or noninvasive intervention indicated.",
                        "synonyms": ["Grade 2", "Moderate"],
                        "ordinal": 2,
                    },
                    {
                        "code": "C41340",
                        "submission_value": "3",
                        "preferred_term": "Grade 3",
                        "definition": "Severe or medically significant but not immediately life-threatening.",
                        "synonyms": ["Grade 3", "Severe"],
                        "ordinal": 3,
                    },
                    {
                        "code": "C41337",
                        "submission_value": "4",
                        "preferred_term": "Grade 4",
                        "definition": "Life-threatening consequences; urgent intervention indicated.",
                        "synonyms": ["Grade 4", "Life-threatening"],
                        "ordinal": 4,
                    },
                    {
                        "code": "C48275",
                        "submission_value": "5",
                        "preferred_term": "Grade 5",
                        "definition": "Death related to adverse event.",
                        "synonyms": ["Grade 5", "Death", "Fatal"],
                        "ordinal": 5,
                    },
                ],
            },
            # =================================================================
            # AESER (C66770) - Serious Event
            # =================================================================
            {
                "c_code": "C66770",
                "name": "Serious Event",
                "submission_value": "AESER",
                "definition": "Indicates whether the adverse event is serious.",
                "codelist_type": "non-extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C49488",
                        "submission_value": "Y",
                        "preferred_term": "Yes",
                        "definition": "The adverse event is serious.",
                        "synonyms": ["Yes", "Serious"],
                    },
                    {
                        "code": "C49487",
                        "submission_value": "N",
                        "preferred_term": "No",
                        "definition": "The adverse event is not serious.",
                        "synonyms": ["No", "Not Serious"],
                    },
                ],
            },
            # =================================================================
            # AEREL (C66771) - Causality
            # =================================================================
            {
                "c_code": "C66771",
                "name": "Causality",
                "submission_value": "AEREL",
                "definition": "The relationship between the adverse event and the study treatment.",
                "codelist_type": "extensible",
                "domain": "AE",
                "terms": [
                    {
                        "code": "C53256",
                        "submission_value": "RELATED",
                        "preferred_term": "Related",
                        "definition": "The adverse event is related to the study treatment.",
                        "synonyms": ["Related", "Drug-Related"],
                    },
                    {
                        "code": "C53257",
                        "submission_value": "NOT RELATED",
                        "preferred_term": "Not Related",
                        "definition": "The adverse event is not related to the study treatment.",
                        "synonyms": ["Not Related", "Unrelated"],
                    },
                    {
                        "code": "C53258",
                        "submission_value": "POSSIBLY RELATED",
                        "preferred_term": "Possibly Related",
                        "definition": "The adverse event may be related to the study treatment.",
                        "synonyms": ["Possibly", "Possible"],
                    },
                    {
                        "code": "C53259",
                        "submission_value": "PROBABLY RELATED",
                        "preferred_term": "Probably Related",
                        "definition": "The adverse event is probably related to the study treatment.",
                        "synonyms": ["Probably", "Probable"],
                    },
                    {
                        "code": "C53260",
                        "submission_value": "UNLIKELY RELATED",
                        "preferred_term": "Unlikely Related",
                        "definition": "The adverse event is unlikely to be related to the study treatment.",
                        "synonyms": ["Unlikely", "Doubtful"],
                    },
                ],
            },
            # =================================================================
            # ROUTE (C66729) - Route of Administration
            # =================================================================
            {
                "c_code": "C66726",
                "name": "Route of Administration",
                "submission_value": "ROUTE",
                "definition": "The route of administration of the treatment.",
                "codelist_type": "extensible",
                "domain": "CM",
                "terms": [
                    {"code": "C38288", "submission_value": "ORAL", "preferred_term": "Oral", "synonyms": ["Oral", "By Mouth", "PO"]},
                    {"code": "C38276", "submission_value": "INTRAVENOUS", "preferred_term": "Intravenous", "synonyms": ["IV", "Intravenous"]},
                    {"code": "C38274", "submission_value": "INTRAMUSCULAR", "preferred_term": "Intramuscular", "synonyms": ["IM", "Intramuscular"]},
                    {"code": "C38299", "submission_value": "SUBCUTANEOUS", "preferred_term": "Subcutaneous", "synonyms": ["SC", "SubQ", "Subcutaneous"]},
                    {"code": "C38305", "submission_value": "TOPICAL", "preferred_term": "Topical", "synonyms": ["Topical", "External"]},
                    {"code": "C38246", "submission_value": "INHALATION", "preferred_term": "Inhalation", "synonyms": ["Inhaled", "Inhalation"]},
                    {"code": "C38292", "submission_value": "RECTAL", "preferred_term": "Rectal", "synonyms": ["Rectal", "PR"]},
                    {"code": "C38287", "submission_value": "OPHTHALMIC", "preferred_term": "Ophthalmic", "synonyms": ["Eye", "Ophthalmic"]},
                    {"code": "C38284", "submission_value": "NASAL", "preferred_term": "Nasal", "synonyms": ["Nasal", "Intranasal"]},
                    {"code": "C38309", "submission_value": "TRANSDERMAL", "preferred_term": "Transdermal", "synonyms": ["Transdermal", "Patch"]},
                    {"code": "C38225", "submission_value": "EPIDURAL", "preferred_term": "Epidural", "synonyms": ["Epidural"]},
                    {"code": "C38268", "submission_value": "INTRATHECAL", "preferred_term": "Intrathecal", "synonyms": ["Intrathecal", "IT"]},
                ],
            },
            # =================================================================
            # UNIT (C71620) - Unit
            # =================================================================
            {
                "c_code": "C71620",
                "name": "Unit",
                "submission_value": "UNIT",
                "definition": "A unit of measure.",
                "codelist_type": "extensible",
                "domain": "GENERAL",
                "terms": [
                    {"code": "C28253", "submission_value": "mg", "preferred_term": "Milligram", "synonyms": ["mg", "milligram"]},
                    {"code": "C28254", "submission_value": "g", "preferred_term": "Gram", "synonyms": ["g", "gram"]},
                    {"code": "C28248", "submission_value": "kg", "preferred_term": "Kilogram", "synonyms": ["kg", "kilogram"]},
                    {"code": "C28252", "submission_value": "mL", "preferred_term": "Milliliter", "synonyms": ["mL", "ml", "milliliter"]},
                    {"code": "C28249", "submission_value": "L", "preferred_term": "Liter", "synonyms": ["L", "liter"]},
                    {"code": "C48155", "submission_value": "ug", "preferred_term": "Microgram", "synonyms": ["ug", "mcg", "microgram"]},
                    {"code": "C67306", "submission_value": "mg/dL", "preferred_term": "Milligram per Deciliter", "synonyms": ["mg/dL"]},
                    {"code": "C67310", "submission_value": "mmol/L", "preferred_term": "Millimole per Liter", "synonyms": ["mmol/L"]},
                    {"code": "C67388", "submission_value": "U/L", "preferred_term": "Unit per Liter", "synonyms": ["U/L", "IU/L"]},
                    {"code": "C48504", "submission_value": "cm", "preferred_term": "Centimeter", "synonyms": ["cm", "centimeter"]},
                    {"code": "C41139", "submission_value": "mm", "preferred_term": "Millimeter", "synonyms": ["mm", "millimeter"]},
                    {"code": "C49670", "submission_value": "mmHg", "preferred_term": "Millimeter of Mercury", "synonyms": ["mmHg"]},
                    {"code": "C49671", "submission_value": "bpm", "preferred_term": "Beats per Minute", "synonyms": ["bpm", "beats/min"]},
                ],
            },
            # =================================================================
            # NY (C66742) - No Yes Response
            # =================================================================
            {
                "c_code": "C66742",
                "name": "No Yes Response",
                "submission_value": "NY",
                "definition": "A response indicating yes or no.",
                "codelist_type": "non-extensible",
                "domain": "GENERAL",
                "terms": [
                    {"code": "C49488", "submission_value": "Y", "preferred_term": "Yes", "synonyms": ["Yes", "True", "1"]},
                    {"code": "C49487", "submission_value": "N", "preferred_term": "No", "synonyms": ["No", "False", "0"]},
                ],
            },
            # =================================================================
            # VSRESU (C66770) - Vital Signs Result Unit
            # =================================================================
            {
                "c_code": "C66770",
                "name": "Vital Signs Result Unit",
                "submission_value": "VSRESU",
                "definition": "Units for vital signs measurements.",
                "codelist_type": "extensible",
                "domain": "VS",
                "terms": [
                    {"code": "C49671", "submission_value": "beats/min", "preferred_term": "Beats per Minute", "synonyms": ["bpm", "beats/min"]},
                    {"code": "C49670", "submission_value": "mmHg", "preferred_term": "Millimeter of Mercury", "synonyms": ["mmHg"]},
                    {"code": "C42559", "submission_value": "C", "preferred_term": "Celsius", "synonyms": ["C", "Celsius", "degrees C"]},
                    {"code": "C44277", "submission_value": "F", "preferred_term": "Fahrenheit", "synonyms": ["F", "Fahrenheit", "degrees F"]},
                    {"code": "C28248", "submission_value": "kg", "preferred_term": "Kilogram", "synonyms": ["kg", "kilogram"]},
                    {"code": "C48504", "submission_value": "cm", "preferred_term": "Centimeter", "synonyms": ["cm", "centimeter"]},
                    {"code": "C49673", "submission_value": "breaths/min", "preferred_term": "Breaths per Minute", "synonyms": ["breaths/min", "rpm"]},
                    {"code": "C25613", "submission_value": "%", "preferred_term": "Percent", "synonyms": ["%", "percent"]},
                    {"code": "C67311", "submission_value": "kg/m2", "preferred_term": "Kilogram per Square Meter", "synonyms": ["kg/m2", "BMI unit"]},
                ],
            },
            # =================================================================
            # VSTEST (C66741) - Vital Signs Test Name
            # =================================================================
            {
                "c_code": "C66741",
                "name": "Vital Signs Test Name",
                "submission_value": "VSTEST",
                "definition": "Names of vital signs tests.",
                "codelist_type": "extensible",
                "domain": "VS",
                "terms": [
                    {"code": "C25298", "submission_value": "DIABP", "preferred_term": "Diastolic Blood Pressure", "synonyms": ["DBP", "Diastolic"]},
                    {"code": "C25299", "submission_value": "SYSBP", "preferred_term": "Systolic Blood Pressure", "synonyms": ["SBP", "Systolic"]},
                    {"code": "C49676", "submission_value": "PULSE", "preferred_term": "Pulse Rate", "synonyms": ["Pulse", "Heart Rate", "HR"]},
                    {"code": "C25208", "submission_value": "TEMP", "preferred_term": "Temperature", "synonyms": ["Temp", "Body Temperature"]},
                    {"code": "C49677", "submission_value": "RESP", "preferred_term": "Respiratory Rate", "synonyms": ["RR", "Respirations"]},
                    {"code": "C16358", "submission_value": "WEIGHT", "preferred_term": "Weight", "synonyms": ["Weight", "Body Weight"]},
                    {"code": "C25347", "submission_value": "HEIGHT", "preferred_term": "Height", "synonyms": ["Height", "Stature"]},
                    {"code": "C16352", "submission_value": "BMI", "preferred_term": "Body Mass Index", "synonyms": ["BMI"]},
                    {"code": "C64798", "submission_value": "OXYSAT", "preferred_term": "Oxygen Saturation", "synonyms": ["SpO2", "O2 Sat"]},
                ],
            },
            # =================================================================
            # DSCAT (C66728) - Disposition Category
            # =================================================================
            {
                "c_code": "C66728",
                "name": "Disposition Category",
                "submission_value": "DSCAT",
                "definition": "Category of disposition event.",
                "codelist_type": "non-extensible",
                "domain": "DS",
                "terms": [
                    {"code": "C49506", "submission_value": "DISPOSITION EVENT", "preferred_term": "Disposition Event", "synonyms": ["Disposition"]},
                    {"code": "C49507", "submission_value": "PROTOCOL MILESTONE", "preferred_term": "Protocol Milestone", "synonyms": ["Milestone"]},
                    {"code": "C49508", "submission_value": "OTHER EVENT", "preferred_term": "Other Event", "synonyms": ["Other"]},
                ],
            },
            # =================================================================
            # DSDECOD (C66727) - Disposition Event
            # =================================================================
            {
                "c_code": "C66727",
                "name": "Disposition Event",
                "submission_value": "DSDECOD",
                "definition": "Standardized disposition terms.",
                "codelist_type": "extensible",
                "domain": "DS",
                "terms": [
                    {"code": "C28554", "submission_value": "COMPLETED", "preferred_term": "Completed", "synonyms": ["Completed", "Finished"]},
                    {"code": "C49516", "submission_value": "ADVERSE EVENT", "preferred_term": "Adverse Event", "synonyms": ["AE", "Adverse Event"]},
                    {"code": "C49517", "submission_value": "DEATH", "preferred_term": "Death", "synonyms": ["Death", "Died"]},
                    {"code": "C49518", "submission_value": "LACK OF EFFICACY", "preferred_term": "Lack of Efficacy", "synonyms": ["Lack of Efficacy", "No Effect"]},
                    {"code": "C49519", "submission_value": "LOST TO FOLLOW-UP", "preferred_term": "Lost to Follow-Up", "synonyms": ["Lost to Follow-Up", "LTFU"]},
                    {"code": "C49520", "submission_value": "PHYSICIAN DECISION", "preferred_term": "Physician Decision", "synonyms": ["Physician Decision"]},
                    {"code": "C49521", "submission_value": "PROTOCOL DEVIATION", "preferred_term": "Protocol Deviation", "synonyms": ["Protocol Deviation"]},
                    {"code": "C49522", "submission_value": "SCREEN FAILURE", "preferred_term": "Screen Failure", "synonyms": ["Screen Failure"]},
                    {"code": "C49523", "submission_value": "WITHDRAWAL BY SUBJECT", "preferred_term": "Withdrawal by Subject", "synonyms": ["Withdrawal", "Subject Withdrew"]},
                ],
            },
            # =================================================================
            # LBTESTCD (C65047) - Laboratory Test Code
            # =================================================================
            {
                "c_code": "C65047",
                "name": "Laboratory Test Code",
                "submission_value": "LBTESTCD",
                "definition": "Codes for laboratory tests.",
                "codelist_type": "extensible",
                "domain": "LB",
                "terms": [
                    {"code": "C64547", "submission_value": "ALB", "preferred_term": "Albumin", "synonyms": ["Albumin"]},
                    {"code": "C64548", "submission_value": "ALP", "preferred_term": "Alkaline Phosphatase", "synonyms": ["Alk Phos", "ALP"]},
                    {"code": "C64549", "submission_value": "ALT", "preferred_term": "Alanine Aminotransferase", "synonyms": ["ALT", "SGPT"]},
                    {"code": "C64550", "submission_value": "AST", "preferred_term": "Aspartate Aminotransferase", "synonyms": ["AST", "SGOT"]},
                    {"code": "C64554", "submission_value": "BILI", "preferred_term": "Bilirubin", "synonyms": ["Bilirubin", "Total Bilirubin"]},
                    {"code": "C64551", "submission_value": "BUN", "preferred_term": "Blood Urea Nitrogen", "synonyms": ["BUN", "Urea Nitrogen"]},
                    {"code": "C64552", "submission_value": "CA", "preferred_term": "Calcium", "synonyms": ["Calcium", "Ca"]},
                    {"code": "C64553", "submission_value": "CHOL", "preferred_term": "Cholesterol", "synonyms": ["Cholesterol", "Total Cholesterol"]},
                    {"code": "C64555", "submission_value": "CREAT", "preferred_term": "Creatinine", "synonyms": ["Creatinine", "Cr"]},
                    {"code": "C64556", "submission_value": "GLUC", "preferred_term": "Glucose", "synonyms": ["Glucose", "Blood Glucose"]},
                    {"code": "C64557", "submission_value": "HBA1C", "preferred_term": "Hemoglobin A1C", "synonyms": ["HbA1c", "A1C", "Glycated Hemoglobin"]},
                    {"code": "C64558", "submission_value": "HGB", "preferred_term": "Hemoglobin", "synonyms": ["Hemoglobin", "Hgb", "Hb"]},
                    {"code": "C64559", "submission_value": "HCT", "preferred_term": "Hematocrit", "synonyms": ["Hematocrit", "Hct"]},
                    {"code": "C64560", "submission_value": "K", "preferred_term": "Potassium", "synonyms": ["Potassium", "K"]},
                    {"code": "C64561", "submission_value": "NA", "preferred_term": "Sodium", "synonyms": ["Sodium", "Na"]},
                    {"code": "C64562", "submission_value": "PLAT", "preferred_term": "Platelet Count", "synonyms": ["Platelets", "PLT"]},
                    {"code": "C64563", "submission_value": "WBC", "preferred_term": "White Blood Cell Count", "synonyms": ["WBC", "Leukocytes"]},
                    {"code": "C64564", "submission_value": "RBC", "preferred_term": "Red Blood Cell Count", "synonyms": ["RBC", "Erythrocytes"]},
                ],
            },
        ]

    # ========================================================================
    # Public API: Codelist Operations
    # ========================================================================

    def get_codelist(self, c_code: str) -> Codelist | None:
        """Get a codelist by its C-code.

        Args:
            c_code: NCI C-code (e.g., "C66731")

        Returns:
            Codelist or None if not found
        """
        return self._codelists.get(c_code.upper())

    def get_codelist_by_name(self, submission_value: str) -> Codelist | None:
        """Get a codelist by its submission value name.

        Args:
            submission_value: Codelist short name (e.g., "SEX", "RACE")

        Returns:
            Codelist or None if not found
        """
        c_code = self._by_submission_value.get(submission_value.upper())
        if c_code:
            return self._codelists.get(c_code)
        return None

    def list_codelists(
        self,
        domain: CDISCDomain | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Codelist]:
        """List codelists with optional filtering.

        Args:
            domain: Filter by SDTM domain
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of codelists
        """
        if domain:
            c_codes = self._by_domain.get(domain, [])
            codelists = [self._codelists[c] for c in c_codes if c in self._codelists]
        else:
            codelists = list(self._codelists.values())

        # Sort by submission value
        codelists.sort(key=lambda x: x.submission_value)

        return codelists[offset:offset + limit]

    def get_codelists_for_domain(self, domain: str | CDISCDomain) -> list[Codelist]:
        """Get all codelists associated with a domain.

        Args:
            domain: SDTM domain name or CDISCDomain enum

        Returns:
            List of codelists for that domain
        """
        if isinstance(domain, str):
            try:
                domain = CDISCDomain[domain.upper()]
            except KeyError:
                return []

        c_codes = self._by_domain.get(domain, [])
        return [self._codelists[c] for c in c_codes if c in self._codelists]

    def get_terms(self, c_code: str) -> list[CodelistTerm]:
        """Get all terms for a codelist.

        Args:
            c_code: Codelist C-code

        Returns:
            List of terms
        """
        codelist = self.get_codelist(c_code)
        if codelist:
            return codelist.terms
        return []

    # ========================================================================
    # Public API: Validation
    # ========================================================================

    def validate_term(
        self,
        codelist_code: str,
        value: str,
        strict: bool = True,
    ) -> ValidationResult:
        """Validate a term against a codelist.

        Args:
            codelist_code: C-code or submission value of the codelist
            value: The value to validate
            strict: If True, non-extensible codelists reject unknown values

        Returns:
            ValidationResult with match details
        """
        # Try to get codelist by C-code first, then by name
        codelist = self.get_codelist(codelist_code)
        if not codelist:
            codelist = self.get_codelist_by_name(codelist_code)

        if not codelist:
            return ValidationResult(
                is_valid=False,
                codelist_code=codelist_code,
                codelist_name="",
                submitted_value=value,
                message=f"Codelist '{codelist_code}' not found",
            )

        value_upper = value.upper().strip()

        # Check for exact match on submission value
        for term in codelist.terms:
            if term.submission_value.upper() == value_upper:
                return ValidationResult(
                    is_valid=True,
                    codelist_code=codelist.c_code,
                    codelist_name=codelist.name,
                    submitted_value=value,
                    matched_term=term,
                    message="Exact match found",
                    is_extensible=codelist.codelist_type == CodelistType.EXTENSIBLE,
                )

        # Check for match on preferred term or synonyms
        for term in codelist.terms:
            if term.preferred_term.upper() == value_upper:
                return ValidationResult(
                    is_valid=True,
                    codelist_code=codelist.c_code,
                    codelist_name=codelist.name,
                    submitted_value=value,
                    matched_term=term,
                    message=f"Matched preferred term. Use submission value: {term.submission_value}",
                    is_extensible=codelist.codelist_type == CodelistType.EXTENSIBLE,
                )
            for synonym in term.synonyms:
                if synonym.upper() == value_upper:
                    return ValidationResult(
                        is_valid=True,
                        codelist_code=codelist.c_code,
                        codelist_name=codelist.name,
                        submitted_value=value,
                        matched_term=term,
                        message=f"Matched synonym. Use submission value: {term.submission_value}",
                        is_extensible=codelist.codelist_type == CodelistType.EXTENSIBLE,
                    )

        # No match found
        is_extensible = codelist.codelist_type == CodelistType.EXTENSIBLE

        # Find similar terms as suggestions
        suggestions = self._find_similar_terms(codelist, value)

        if is_extensible and not strict:
            return ValidationResult(
                is_valid=True,
                codelist_code=codelist.c_code,
                codelist_name=codelist.name,
                submitted_value=value,
                message="Value not in codelist but codelist is extensible",
                is_extensible=True,
                suggestions=suggestions,
            )

        return ValidationResult(
            is_valid=False,
            codelist_code=codelist.c_code,
            codelist_name=codelist.name,
            submitted_value=value,
            message=f"Value '{value}' not found in {'extensible ' if is_extensible else ''}codelist '{codelist.name}'",
            is_extensible=is_extensible,
            suggestions=suggestions,
        )

    def _find_similar_terms(self, codelist: Codelist, value: str, max_results: int = 5) -> list[CodelistTerm]:
        """Find terms similar to the given value."""
        value_lower = value.lower()
        scored_terms: list[tuple[float, CodelistTerm]] = []

        for term in codelist.terms:
            # Calculate simple similarity score
            max_score = 0.0

            # Check submission value
            sv_lower = term.submission_value.lower()
            if value_lower in sv_lower or sv_lower in value_lower:
                score = len(value_lower) / max(len(sv_lower), len(value_lower))
                max_score = max(max_score, score)

            # Check preferred term
            pt_lower = term.preferred_term.lower()
            if value_lower in pt_lower or pt_lower in value_lower:
                score = len(value_lower) / max(len(pt_lower), len(value_lower))
                max_score = max(max_score, score)

            # Check synonyms
            for synonym in term.synonyms:
                syn_lower = synonym.lower()
                if value_lower in syn_lower or syn_lower in value_lower:
                    score = len(value_lower) / max(len(syn_lower), len(value_lower))
                    max_score = max(max_score, score)

            if max_score > 0.3:
                scored_terms.append((max_score, term))

        scored_terms.sort(key=lambda x: -x[0])
        return [term for _, term in scored_terms[:max_results]]

    # ========================================================================
    # Public API: Search
    # ========================================================================

    def search_codelists(
        self,
        query: str,
        domain: CDISCDomain | None = None,
        limit: int = 20,
    ) -> list[Codelist]:
        """Search codelists by name or submission value.

        Args:
            query: Search query
            domain: Optional domain filter
            limit: Maximum results

        Returns:
            List of matching codelists
        """
        query_lower = query.lower().strip()
        results: list[Codelist] = []

        for codelist in self._codelists.values():
            if domain and codelist.domain != domain:
                continue

            # Match on name, submission value, or definition
            if (query_lower in codelist.name.lower() or
                query_lower in codelist.submission_value.lower() or
                query_lower in codelist.definition.lower()):
                results.append(codelist)

            if len(results) >= limit:
                break

        return results

    def search_terms(
        self,
        query: str,
        codelist_code: str | None = None,
        limit: int = 50,
    ) -> list[tuple[Codelist, CodelistTerm]]:
        """Search for terms across codelists.

        Args:
            query: Search query
            codelist_code: Optional codelist filter
            limit: Maximum results

        Returns:
            List of (codelist, term) tuples
        """
        query_lower = query.lower().strip()
        results: list[tuple[Codelist, CodelistTerm]] = []

        # Search in term index first
        if query_lower in self._term_index:
            for cl_code, term_code in self._term_index[query_lower]:
                if codelist_code and cl_code != codelist_code.upper():
                    continue
                codelist = self._codelists.get(cl_code)
                if codelist:
                    for term in codelist.terms:
                        if term.code == term_code:
                            results.append((codelist, term))
                            break
                if len(results) >= limit:
                    return results

        # Also do partial matching
        if codelist_code:
            codelists = [self.get_codelist(codelist_code)] if self.get_codelist(codelist_code) else []
        else:
            codelists = list(self._codelists.values())

        for codelist in codelists:
            if codelist is None:
                continue
            for term in codelist.terms:
                if len(results) >= limit:
                    return results
                if (query_lower in term.submission_value.lower() or
                    query_lower in term.preferred_term.lower() or
                    any(query_lower in s.lower() for s in term.synonyms)):
                    if (codelist, term) not in results:
                        results.append((codelist, term))

        return results

    # ========================================================================
    # Public API: Domain Operations
    # ========================================================================

    def list_domains(self) -> list[dict[str, Any]]:
        """List all SDTM domains with their codelist counts.

        Returns:
            List of domain info dictionaries
        """
        domain_info = []
        for domain in CDISCDomain:
            c_codes = self._by_domain.get(domain, [])
            domain_info.append({
                "domain": domain.name,
                "description": domain.value,
                "codelist_count": len(c_codes),
                "codelists": c_codes,
            })
        return domain_info

    # ========================================================================
    # Public API: Version Management
    # ========================================================================

    def list_versions(self) -> list[CDISCVersion]:
        """List available CT versions.

        Returns:
            List of version objects
        """
        return sorted(self._versions.values(), key=lambda v: v.version, reverse=True)

    def get_current_version(self) -> str:
        """Get the current/default CT version."""
        return self._current_version

    # ========================================================================
    # Public API: Statistics
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the terminology database."""
        total_terms = sum(len(cl.terms) for cl in self._codelists.values())
        extensible_count = sum(1 for cl in self._codelists.values() if cl.codelist_type == CodelistType.EXTENSIBLE)

        by_domain: dict[str, int] = {}
        for domain, c_codes in self._by_domain.items():
            by_domain[domain.name] = len(c_codes)

        return {
            "total_codelists": len(self._codelists),
            "total_terms": total_terms,
            "extensible_codelists": extensible_count,
            "non_extensible_codelists": len(self._codelists) - extensible_count,
            "current_version": self._current_version,
            "available_versions": list(self._versions.keys()),
            "by_domain": by_domain,
        }

    def get_codelist_summary(self, c_code: str) -> dict[str, Any] | None:
        """Get a summary of a codelist for API responses.

        Args:
            c_code: Codelist C-code

        Returns:
            Dictionary with codelist summary or None
        """
        codelist = self.get_codelist(c_code)
        if not codelist:
            return None

        return {
            "c_code": codelist.c_code,
            "name": codelist.name,
            "submission_value": codelist.submission_value,
            "definition": codelist.definition,
            "codelist_type": codelist.codelist_type.value,
            "domain": codelist.domain.name,
            "term_count": len(codelist.terms),
            "version": codelist.version,
            "related_codelists": codelist.related_codelists,
        }
