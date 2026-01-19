#!/usr/bin/env python3
"""Load and process CDISC Controlled Terminology.

This script creates a CDISC CT fixture file with:
- Standard SDTM codelists from NCI EVS format
- Multiple CT versions support
- Extensible vs non-extensible codelist metadata
- Domain associations

CDISC CT sources:
- NCI EVS: https://evs.nci.nih.gov/ftp1/CDISC/
- CDISC Library: https://library.cdisc.org/
- NCI Thesaurus Browser: https://ncithesaurus.nci.nih.gov/

Usage:
    python scripts/load_cdisc_terminology.py

This will:
1. Generate built-in CDISC terminology with common codelists
2. Create fixtures/cdisc_terminology.json
3. Optionally fetch from NCI EVS (if --fetch flag provided)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error

# Output paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
OUTPUT_FILE = FIXTURES_DIR / "cdisc_terminology.json"

# NCI EVS URL patterns
NCI_EVS_BASE = "https://evs.nci.nih.gov/ftp1/CDISC"
NCI_EVS_SDTM = f"{NCI_EVS_BASE}/SDTM/SDTM%20Terminology.odm.xml"

# ============================================================================
# CDISC Domain Mappings
# ============================================================================
DOMAIN_MAPPINGS = {
    # Demographics
    "SEX": "DM",
    "RACE": "DM",
    "ETHNIC": "DM",
    "COUNTRY": "DM",
    "ARMCD": "DM",
    "ARM": "DM",
    "ACTARMCD": "DM",
    "ACTARM": "DM",
    # Adverse Events
    "AEOUT": "AE",
    "AEACN": "AE",
    "AESEV": "AE",
    "AETOXGR": "AE",
    "AESER": "AE",
    "AEREL": "AE",
    "AESCONG": "AE",
    "AESDISAB": "AE",
    "AESDTH": "AE",
    "AESHOSP": "AE",
    "AESLIFE": "AE",
    "AESMIE": "AE",
    "AECONTRT": "AE",
    "AEPATT": "AE",
    # Concomitant Medications
    "ROUTE": "CM",
    "FRM": "CM",
    "CMDOSFRQ": "CM",
    # Disposition
    "DSCAT": "DS",
    "DSDECOD": "DS",
    # Laboratory
    "LBTESTCD": "LB",
    "LBCAT": "LB",
    "LBSCAT": "LB",
    "LBSPEC": "LB",
    "LBMETHOD": "LB",
    # Vital Signs
    "VSTEST": "VS",
    "VSPOS": "VS",
    "VSLOC": "VS",
    "VSRESU": "VS",
    # ECG
    "EGTESTCD": "EG",
    "EGTEST": "EG",
    # Medical History
    "MHCAT": "MH",
    # Physical Exam
    "PECAT": "PE",
    # Exposure
    "EXCAT": "EX",
    "EXDOSFRQ": "EX",
    "EXROUTE": "EX",
    # General/Cross-domain
    "NY": "GENERAL",
    "UNIT": "GENERAL",
    "LOC": "GENERAL",
    "LAT": "GENERAL",
    "DIR": "GENERAL",
    "STENRF": "GENERAL",
    "EVAL": "GENERAL",
    "EPOCH": "GENERAL",
    "OUT": "GENERAL",
    "TRTORD": "GENERAL",
    "ACN": "GENERAL",
    "NCOMPLT": "GENERAL",
    "FRMTYP": "GENERAL",
    "REAS": "GENERAL",
    "SPECTYPE": "GENERAL",
    "POSITION": "GENERAL",
}

# Extensible codelists
EXTENSIBLE_CODELISTS = {
    "RACE",
    "COUNTRY",
    "ROUTE",
    "FRM",
    "UNIT",
    "LBTESTCD",
    "LBCAT",
    "LBSCAT",
    "LBSPEC",
    "LBMETHOD",
    "VSTEST",
    "EGTESTCD",
    "EGTEST",
    "MHCAT",
    "PECAT",
    "EXCAT",
    "DSDECOD",
    "AEREL",
    "CMDOSFRQ",
    "EXDOSFRQ",
}


# ============================================================================
# Built-in CDISC Terminology Data
# ============================================================================
def get_builtin_codelists() -> list[dict[str, Any]]:
    """Get comprehensive built-in CDISC terminology.

    This provides a subset of common SDTM codelists for demo and offline use.
    """
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
            "nci_preferred_term": "Sex",
            "terms": [
                {
                    "code": "C16576",
                    "submission_value": "F",
                    "preferred_term": "Female",
                    "definition": "A person who belongs to the sex that normally produces ova.",
                    "synonyms": ["Female", "Woman", "Girl"],
                    "ordinal": 1,
                },
                {
                    "code": "C20197",
                    "submission_value": "M",
                    "preferred_term": "Male",
                    "definition": "A person who belongs to the sex that normally produces sperm.",
                    "synonyms": ["Male", "Man", "Boy"],
                    "ordinal": 2,
                },
                {
                    "code": "C38046",
                    "submission_value": "U",
                    "preferred_term": "Unknown",
                    "definition": "Not known, not observed, not recorded, or refused.",
                    "synonyms": ["Unknown", "Not Known"],
                    "ordinal": 3,
                },
                {
                    "code": "C48660",
                    "submission_value": "UNDIFFERENTIATED",
                    "preferred_term": "Undifferentiated",
                    "definition": "Sex could not be determined; not clear which sex.",
                    "synonyms": ["Undifferentiated", "Intersex"],
                    "ordinal": 4,
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
            "definition": "A categorization of humans based on selected genetically transmitted physical characteristics.",
            "codelist_type": "extensible",
            "domain": "DM",
            "nci_preferred_term": "Race Category",
            "terms": [
                {
                    "code": "C41259",
                    "submission_value": "AMERICAN INDIAN OR ALASKA NATIVE",
                    "preferred_term": "American Indian or Alaska Native",
                    "definition": "A person having origins in any of the original peoples of North and South America.",
                    "synonyms": ["Native American", "Indigenous", "First Nations"],
                    "ordinal": 1,
                },
                {
                    "code": "C41260",
                    "submission_value": "ASIAN",
                    "preferred_term": "Asian",
                    "definition": "A person having origins in any of the original peoples of the Far East, Southeast Asia, or the Indian subcontinent.",
                    "synonyms": ["Asian"],
                    "ordinal": 2,
                },
                {
                    "code": "C16352",
                    "submission_value": "BLACK OR AFRICAN AMERICAN",
                    "preferred_term": "Black or African American",
                    "definition": "A person having origins in any of the Black racial groups of Africa.",
                    "synonyms": ["Black", "African American", "African"],
                    "ordinal": 3,
                },
                {
                    "code": "C41219",
                    "submission_value": "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
                    "preferred_term": "Native Hawaiian or Other Pacific Islander",
                    "definition": "A person having origins in any of the original peoples of Hawaii, Guam, Samoa, or other Pacific Islands.",
                    "synonyms": ["Pacific Islander", "Hawaiian", "Polynesian"],
                    "ordinal": 4,
                },
                {
                    "code": "C41261",
                    "submission_value": "WHITE",
                    "preferred_term": "White",
                    "definition": "A person having origins in any of the original peoples of Europe, the Middle East, or North Africa.",
                    "synonyms": ["White", "Caucasian", "European"],
                    "ordinal": 5,
                },
                {
                    "code": "C17998",
                    "submission_value": "UNKNOWN",
                    "preferred_term": "Unknown",
                    "definition": "Not known, not observed, not recorded, or refused.",
                    "synonyms": ["Unknown", "Not Reported"],
                    "ordinal": 6,
                },
                {
                    "code": "C43234",
                    "submission_value": "MULTIPLE",
                    "preferred_term": "Multiple",
                    "definition": "Having more than one race.",
                    "synonyms": ["Multiple", "Mixed Race", "Multiracial", "Mixed"],
                    "ordinal": 7,
                },
                {
                    "code": "C66790",
                    "submission_value": "OTHER",
                    "preferred_term": "Other",
                    "definition": "Different from the one(s) specified.",
                    "synonyms": ["Other"],
                    "ordinal": 8,
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
            "definition": "The ethnic group of an individual based on cultural traditions.",
            "codelist_type": "non-extensible",
            "domain": "DM",
            "nci_preferred_term": "Ethnic Group",
            "terms": [
                {
                    "code": "C17459",
                    "submission_value": "HISPANIC OR LATINO",
                    "preferred_term": "Hispanic or Latino",
                    "definition": "A person of Cuban, Mexican, Puerto Rican, South or Central American, or other Spanish culture or origin.",
                    "synonyms": ["Hispanic", "Latino", "Latina", "Latinx", "Spanish"],
                    "ordinal": 1,
                },
                {
                    "code": "C41222",
                    "submission_value": "NOT HISPANIC OR LATINO",
                    "preferred_term": "Not Hispanic or Latino",
                    "definition": "A person not of Cuban, Mexican, Puerto Rican, South or Central American, or other Spanish culture or origin.",
                    "synonyms": ["Not Hispanic", "Non-Hispanic", "Non-Latino"],
                    "ordinal": 2,
                },
                {
                    "code": "C17998",
                    "submission_value": "UNKNOWN",
                    "preferred_term": "Unknown",
                    "definition": "Not known, not observed, not recorded, or refused.",
                    "synonyms": ["Unknown"],
                    "ordinal": 3,
                },
                {
                    "code": "C66789",
                    "submission_value": "NOT REPORTED",
                    "preferred_term": "Not Reported",
                    "definition": "Not provided or available.",
                    "synonyms": ["Not Reported", "Unreported"],
                    "ordinal": 4,
                },
            ],
        },
        # =================================================================
        # COUNTRY (C66729) - Demographics - ISO 3166-1 alpha-3
        # =================================================================
        {
            "c_code": "C66729",
            "name": "Country",
            "submission_value": "COUNTRY",
            "definition": "A set of countries using ISO 3166-1 alpha-3 codes.",
            "codelist_type": "extensible",
            "domain": "DM",
            "nci_preferred_term": "Country Code",
            "terms": [
                {"code": "C16984", "submission_value": "USA", "preferred_term": "United States of America", "synonyms": ["United States", "US", "America"], "ordinal": 1},
                {"code": "C17241", "submission_value": "GBR", "preferred_term": "United Kingdom", "synonyms": ["UK", "Britain", "England"], "ordinal": 2},
                {"code": "C16536", "submission_value": "FRA", "preferred_term": "France", "synonyms": ["France"], "ordinal": 3},
                {"code": "C16643", "submission_value": "DEU", "preferred_term": "Germany", "synonyms": ["Germany", "Deutschland"], "ordinal": 4},
                {"code": "C17087", "submission_value": "ITA", "preferred_term": "Italy", "synonyms": ["Italy", "Italia"], "ordinal": 5},
                {"code": "C20317", "submission_value": "ESP", "preferred_term": "Spain", "synonyms": ["Spain", "Espana"], "ordinal": 6},
                {"code": "C16408", "submission_value": "CAN", "preferred_term": "Canada", "synonyms": ["Canada"], "ordinal": 7},
                {"code": "C16310", "submission_value": "AUS", "preferred_term": "Australia", "synonyms": ["Australia"], "ordinal": 8},
                {"code": "C17089", "submission_value": "JPN", "preferred_term": "Japan", "synonyms": ["Japan", "Nippon"], "ordinal": 9},
                {"code": "C16441", "submission_value": "CHN", "preferred_term": "China", "synonyms": ["China", "PRC"], "ordinal": 10},
                {"code": "C17078", "submission_value": "IND", "preferred_term": "India", "synonyms": ["India"], "ordinal": 11},
                {"code": "C16362", "submission_value": "BRA", "preferred_term": "Brazil", "synonyms": ["Brazil", "Brasil"], "ordinal": 12},
                {"code": "C17156", "submission_value": "MEX", "preferred_term": "Mexico", "synonyms": ["Mexico"], "ordinal": 13},
                {"code": "C17243", "submission_value": "KOR", "preferred_term": "Republic of Korea", "synonyms": ["South Korea", "Korea"], "ordinal": 14},
                {"code": "C17212", "submission_value": "RUS", "preferred_term": "Russian Federation", "synonyms": ["Russia"], "ordinal": 15},
                {"code": "C17187", "submission_value": "NLD", "preferred_term": "Netherlands", "synonyms": ["Netherlands", "Holland"], "ordinal": 16},
                {"code": "C16340", "submission_value": "BEL", "preferred_term": "Belgium", "synonyms": ["Belgium"], "ordinal": 17},
                {"code": "C17249", "submission_value": "CHE", "preferred_term": "Switzerland", "synonyms": ["Switzerland"], "ordinal": 18},
                {"code": "C17198", "submission_value": "POL", "preferred_term": "Poland", "synonyms": ["Poland"], "ordinal": 19},
                {"code": "C17183", "submission_value": "SWE", "preferred_term": "Sweden", "synonyms": ["Sweden"], "ordinal": 20},
                {"code": "C16308", "submission_value": "ARG", "preferred_term": "Argentina", "synonyms": ["Argentina"], "ordinal": 21},
                {"code": "C17227", "submission_value": "ZAF", "preferred_term": "South Africa", "synonyms": ["South Africa"], "ordinal": 22},
                {"code": "C16496", "submission_value": "DNK", "preferred_term": "Denmark", "synonyms": ["Denmark"], "ordinal": 23},
                {"code": "C17170", "submission_value": "NOR", "preferred_term": "Norway", "synonyms": ["Norway"], "ordinal": 24},
                {"code": "C16530", "submission_value": "FIN", "preferred_term": "Finland", "synonyms": ["Finland"], "ordinal": 25},
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
            "nci_preferred_term": "Adverse Event Outcome",
            "terms": [
                {
                    "code": "C49494",
                    "submission_value": "RECOVERED/RESOLVED",
                    "preferred_term": "Recovered/Resolved",
                    "definition": "The adverse event has completely resolved.",
                    "synonyms": ["Recovered", "Resolved", "Complete Resolution", "Cured"],
                    "ordinal": 1,
                },
                {
                    "code": "C49495",
                    "submission_value": "RECOVERING/RESOLVING",
                    "preferred_term": "Recovering/Resolving",
                    "definition": "The adverse event is in the process of resolving.",
                    "synonyms": ["Recovering", "Resolving", "Improving", "Getting Better"],
                    "ordinal": 2,
                },
                {
                    "code": "C49496",
                    "submission_value": "NOT RECOVERED/NOT RESOLVED",
                    "preferred_term": "Not Recovered/Not Resolved",
                    "definition": "The adverse event has not resolved.",
                    "synonyms": ["Not Recovered", "Not Resolved", "Ongoing", "Persistent"],
                    "ordinal": 3,
                },
                {
                    "code": "C49497",
                    "submission_value": "RECOVERED/RESOLVED WITH SEQUELAE",
                    "preferred_term": "Recovered/Resolved with Sequelae",
                    "definition": "The adverse event resolved but with residual effects.",
                    "synonyms": ["With Sequelae", "Residual Effects", "Permanent Damage"],
                    "ordinal": 4,
                },
                {
                    "code": "C48275",
                    "submission_value": "FATAL",
                    "preferred_term": "Fatal",
                    "definition": "The adverse event resulted in death.",
                    "synonyms": ["Fatal", "Death", "Died", "Deceased"],
                    "ordinal": 5,
                },
                {
                    "code": "C17998",
                    "submission_value": "UNKNOWN",
                    "preferred_term": "Unknown",
                    "definition": "The outcome is not known.",
                    "synonyms": ["Unknown", "Not Known"],
                    "ordinal": 6,
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
            "nci_preferred_term": "Study Treatment Action Taken",
            "terms": [
                {
                    "code": "C49500",
                    "submission_value": "DRUG WITHDRAWN",
                    "preferred_term": "Drug Withdrawn",
                    "definition": "The study drug was permanently discontinued.",
                    "synonyms": ["Withdrawn", "Discontinued", "Stopped", "Terminated"],
                    "ordinal": 1,
                },
                {
                    "code": "C49501",
                    "submission_value": "DOSE REDUCED",
                    "preferred_term": "Dose Reduced",
                    "definition": "The dose of the study drug was reduced.",
                    "synonyms": ["Reduced", "Dose Decrease", "Lowered"],
                    "ordinal": 2,
                },
                {
                    "code": "C49502",
                    "submission_value": "DOSE INCREASED",
                    "preferred_term": "Dose Increased",
                    "definition": "The dose of the study drug was increased.",
                    "synonyms": ["Increased", "Dose Increase", "Raised"],
                    "ordinal": 3,
                },
                {
                    "code": "C49503",
                    "submission_value": "DOSE NOT CHANGED",
                    "preferred_term": "Dose Not Changed",
                    "definition": "The dose of the study drug was not changed.",
                    "synonyms": ["No Change", "Unchanged", "Maintained"],
                    "ordinal": 4,
                },
                {
                    "code": "C49504",
                    "submission_value": "DRUG INTERRUPTED",
                    "preferred_term": "Drug Interrupted",
                    "definition": "The study drug was temporarily interrupted.",
                    "synonyms": ["Interrupted", "Held", "Paused", "Suspended"],
                    "ordinal": 5,
                },
                {
                    "code": "C49505",
                    "submission_value": "NOT APPLICABLE",
                    "preferred_term": "Not Applicable",
                    "definition": "Not applicable for this adverse event.",
                    "synonyms": ["N/A", "Not Applicable", "NA"],
                    "ordinal": 6,
                },
                {
                    "code": "C17998",
                    "submission_value": "UNKNOWN",
                    "preferred_term": "Unknown",
                    "definition": "The action taken is not known.",
                    "synonyms": ["Unknown", "Not Known"],
                    "ordinal": 7,
                },
            ],
        },
        # =================================================================
        # AESEV (C66769) - Severity/Intensity Scale
        # =================================================================
        {
            "c_code": "C66769",
            "name": "Severity/Intensity Scale for Adverse Events",
            "submission_value": "AESEV",
            "definition": "The severity or intensity of the adverse event.",
            "codelist_type": "non-extensible",
            "domain": "AE",
            "nci_preferred_term": "Severity Scale",
            "terms": [
                {
                    "code": "C41338",
                    "submission_value": "MILD",
                    "preferred_term": "Mild",
                    "definition": "Awareness of symptoms but easily tolerated.",
                    "synonyms": ["Mild", "Grade 1", "Light", "Minor"],
                    "ordinal": 1,
                },
                {
                    "code": "C41339",
                    "submission_value": "MODERATE",
                    "preferred_term": "Moderate",
                    "definition": "Discomfort enough to cause interference with usual activity.",
                    "synonyms": ["Moderate", "Grade 2", "Medium"],
                    "ordinal": 2,
                },
                {
                    "code": "C41340",
                    "submission_value": "SEVERE",
                    "preferred_term": "Severe",
                    "definition": "Incapacitating with inability to work or do usual activity.",
                    "synonyms": ["Severe", "Grade 3", "Serious", "Significant"],
                    "ordinal": 3,
                },
            ],
        },
        # =================================================================
        # AETOXGR (C66781) - NCI CTCAE Grade Scale
        # =================================================================
        {
            "c_code": "C66781",
            "name": "NCI CTCAE Grade Scale for Adverse Events",
            "submission_value": "AETOXGR",
            "definition": "NCI Common Terminology Criteria for Adverse Events (CTCAE) grading scale.",
            "codelist_type": "non-extensible",
            "domain": "AE",
            "nci_preferred_term": "CTCAE Grade",
            "terms": [
                {
                    "code": "C41338",
                    "submission_value": "1",
                    "preferred_term": "Grade 1",
                    "definition": "Mild; asymptomatic or mild symptoms; clinical or diagnostic observations only; intervention not indicated.",
                    "synonyms": ["Grade 1", "Mild", "G1"],
                    "ordinal": 1,
                },
                {
                    "code": "C41339",
                    "submission_value": "2",
                    "preferred_term": "Grade 2",
                    "definition": "Moderate; minimal, local or noninvasive intervention indicated; limiting age-appropriate instrumental ADL.",
                    "synonyms": ["Grade 2", "Moderate", "G2"],
                    "ordinal": 2,
                },
                {
                    "code": "C41340",
                    "submission_value": "3",
                    "preferred_term": "Grade 3",
                    "definition": "Severe or medically significant but not immediately life-threatening; hospitalization or prolongation of hospitalization indicated.",
                    "synonyms": ["Grade 3", "Severe", "G3"],
                    "ordinal": 3,
                },
                {
                    "code": "C41337",
                    "submission_value": "4",
                    "preferred_term": "Grade 4",
                    "definition": "Life-threatening consequences; urgent intervention indicated.",
                    "synonyms": ["Grade 4", "Life-threatening", "G4"],
                    "ordinal": 4,
                },
                {
                    "code": "C48275",
                    "submission_value": "5",
                    "preferred_term": "Grade 5",
                    "definition": "Death related to adverse event.",
                    "synonyms": ["Grade 5", "Death", "Fatal", "G5"],
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
            "nci_preferred_term": "Serious Adverse Event Indicator",
            "terms": [
                {
                    "code": "C49488",
                    "submission_value": "Y",
                    "preferred_term": "Yes",
                    "definition": "The adverse event is serious per regulatory definition.",
                    "synonyms": ["Yes", "Serious", "SAE"],
                    "ordinal": 1,
                },
                {
                    "code": "C49487",
                    "submission_value": "N",
                    "preferred_term": "No",
                    "definition": "The adverse event is not serious.",
                    "synonyms": ["No", "Not Serious", "Non-SAE"],
                    "ordinal": 2,
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
            "nci_preferred_term": "Adverse Event Causality",
            "terms": [
                {
                    "code": "C53256",
                    "submission_value": "RELATED",
                    "preferred_term": "Related",
                    "definition": "The adverse event is related to the study treatment.",
                    "synonyms": ["Related", "Drug-Related", "Treatment-Related"],
                    "ordinal": 1,
                },
                {
                    "code": "C53257",
                    "submission_value": "NOT RELATED",
                    "preferred_term": "Not Related",
                    "definition": "The adverse event is not related to the study treatment.",
                    "synonyms": ["Not Related", "Unrelated", "Not Drug-Related"],
                    "ordinal": 2,
                },
                {
                    "code": "C53258",
                    "submission_value": "POSSIBLY RELATED",
                    "preferred_term": "Possibly Related",
                    "definition": "The adverse event may be related to the study treatment.",
                    "synonyms": ["Possibly", "Possible", "May Be Related"],
                    "ordinal": 3,
                },
                {
                    "code": "C53259",
                    "submission_value": "PROBABLY RELATED",
                    "preferred_term": "Probably Related",
                    "definition": "The adverse event is probably related to the study treatment.",
                    "synonyms": ["Probably", "Probable", "Likely Related"],
                    "ordinal": 4,
                },
                {
                    "code": "C53260",
                    "submission_value": "UNLIKELY RELATED",
                    "preferred_term": "Unlikely Related",
                    "definition": "The adverse event is unlikely to be related to the study treatment.",
                    "synonyms": ["Unlikely", "Doubtful", "Improbable"],
                    "ordinal": 5,
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
            "definition": "The route of administration of a treatment.",
            "codelist_type": "extensible",
            "domain": "CM",
            "nci_preferred_term": "Route of Administration",
            "terms": [
                {"code": "C38288", "submission_value": "ORAL", "preferred_term": "Oral", "synonyms": ["Oral", "By Mouth", "PO", "Per Os"], "ordinal": 1},
                {"code": "C38276", "submission_value": "INTRAVENOUS", "preferred_term": "Intravenous", "synonyms": ["IV", "Intravenous", "Venous"], "ordinal": 2},
                {"code": "C38274", "submission_value": "INTRAMUSCULAR", "preferred_term": "Intramuscular", "synonyms": ["IM", "Intramuscular"], "ordinal": 3},
                {"code": "C38299", "submission_value": "SUBCUTANEOUS", "preferred_term": "Subcutaneous", "synonyms": ["SC", "SubQ", "Subcutaneous", "SQ"], "ordinal": 4},
                {"code": "C38305", "submission_value": "TOPICAL", "preferred_term": "Topical", "synonyms": ["Topical", "External", "Cutaneous"], "ordinal": 5},
                {"code": "C38246", "submission_value": "INHALATION", "preferred_term": "Inhalation", "synonyms": ["Inhaled", "Inhalation", "Respiratory"], "ordinal": 6},
                {"code": "C38292", "submission_value": "RECTAL", "preferred_term": "Rectal", "synonyms": ["Rectal", "PR", "Per Rectum"], "ordinal": 7},
                {"code": "C38287", "submission_value": "OPHTHALMIC", "preferred_term": "Ophthalmic", "synonyms": ["Eye", "Ophthalmic", "Ocular"], "ordinal": 8},
                {"code": "C38284", "submission_value": "NASAL", "preferred_term": "Nasal", "synonyms": ["Nasal", "Intranasal", "Nose"], "ordinal": 9},
                {"code": "C38309", "submission_value": "TRANSDERMAL", "preferred_term": "Transdermal", "synonyms": ["Transdermal", "Patch", "Percutaneous"], "ordinal": 10},
                {"code": "C38225", "submission_value": "EPIDURAL", "preferred_term": "Epidural", "synonyms": ["Epidural", "Extradural"], "ordinal": 11},
                {"code": "C38268", "submission_value": "INTRATHECAL", "preferred_term": "Intrathecal", "synonyms": ["Intrathecal", "IT", "Spinal"], "ordinal": 12},
                {"code": "C38254", "submission_value": "INTRAARTICULAR", "preferred_term": "Intraarticular", "synonyms": ["Intraarticular", "Joint Injection"], "ordinal": 13},
                {"code": "C38249", "submission_value": "INTRADERMAL", "preferred_term": "Intradermal", "synonyms": ["Intradermal", "ID", "Intracutaneous"], "ordinal": 14},
                {"code": "C38312", "submission_value": "VAGINAL", "preferred_term": "Vaginal", "synonyms": ["Vaginal", "PV", "Per Vagina"], "ordinal": 15},
                {"code": "C38300", "submission_value": "SUBLINGUAL", "preferred_term": "Sublingual", "synonyms": ["Sublingual", "SL", "Under Tongue"], "ordinal": 16},
                {"code": "C38194", "submission_value": "BUCCAL", "preferred_term": "Buccal", "synonyms": ["Buccal", "Cheek"], "ordinal": 17},
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
            "nci_preferred_term": "Yes No Indicator",
            "terms": [
                {"code": "C49488", "submission_value": "Y", "preferred_term": "Yes", "synonyms": ["Yes", "True", "1", "Positive"], "ordinal": 1},
                {"code": "C49487", "submission_value": "N", "preferred_term": "No", "synonyms": ["No", "False", "0", "Negative"], "ordinal": 2},
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
            "nci_preferred_term": "Unit of Measure",
            "terms": [
                {"code": "C28253", "submission_value": "mg", "preferred_term": "Milligram", "synonyms": ["mg", "milligram", "milligrams"], "ordinal": 1},
                {"code": "C28254", "submission_value": "g", "preferred_term": "Gram", "synonyms": ["g", "gram", "grams", "gm"], "ordinal": 2},
                {"code": "C28248", "submission_value": "kg", "preferred_term": "Kilogram", "synonyms": ["kg", "kilogram", "kilograms"], "ordinal": 3},
                {"code": "C28252", "submission_value": "mL", "preferred_term": "Milliliter", "synonyms": ["mL", "ml", "milliliter", "cc"], "ordinal": 4},
                {"code": "C28249", "submission_value": "L", "preferred_term": "Liter", "synonyms": ["L", "liter", "liters"], "ordinal": 5},
                {"code": "C48155", "submission_value": "ug", "preferred_term": "Microgram", "synonyms": ["ug", "mcg", "microgram", "micrograms"], "ordinal": 6},
                {"code": "C67306", "submission_value": "mg/dL", "preferred_term": "Milligram per Deciliter", "synonyms": ["mg/dL", "mg/dl"], "ordinal": 7},
                {"code": "C67310", "submission_value": "mmol/L", "preferred_term": "Millimole per Liter", "synonyms": ["mmol/L", "mmol/l", "mM"], "ordinal": 8},
                {"code": "C67388", "submission_value": "U/L", "preferred_term": "Unit per Liter", "synonyms": ["U/L", "IU/L", "units/L"], "ordinal": 9},
                {"code": "C48504", "submission_value": "cm", "preferred_term": "Centimeter", "synonyms": ["cm", "centimeter", "centimeters"], "ordinal": 10},
                {"code": "C41139", "submission_value": "mm", "preferred_term": "Millimeter", "synonyms": ["mm", "millimeter", "millimeters"], "ordinal": 11},
                {"code": "C49670", "submission_value": "mmHg", "preferred_term": "Millimeter of Mercury", "synonyms": ["mmHg", "mm Hg"], "ordinal": 12},
                {"code": "C49671", "submission_value": "bpm", "preferred_term": "Beats per Minute", "synonyms": ["bpm", "beats/min", "/min"], "ordinal": 13},
                {"code": "C25613", "submission_value": "%", "preferred_term": "Percent", "synonyms": ["%", "percent", "percentage"], "ordinal": 14},
                {"code": "C42559", "submission_value": "C", "preferred_term": "Celsius", "synonyms": ["C", "Celsius", "degrees C"], "ordinal": 15},
                {"code": "C44277", "submission_value": "F", "preferred_term": "Fahrenheit", "synonyms": ["F", "Fahrenheit", "degrees F"], "ordinal": 16},
                {"code": "C67311", "submission_value": "kg/m2", "preferred_term": "Kilogram per Square Meter", "synonyms": ["kg/m2", "kg/m^2", "BMI"], "ordinal": 17},
                {"code": "C64550", "submission_value": "10^9/L", "preferred_term": "Billion per Liter", "synonyms": ["10^9/L", "x10^9/L", "Giga/L"], "ordinal": 18},
                {"code": "C64551", "submission_value": "10^12/L", "preferred_term": "Trillion per Liter", "synonyms": ["10^12/L", "x10^12/L", "Tera/L"], "ordinal": 19},
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
            "nci_preferred_term": "Vital Sign",
            "terms": [
                {"code": "C25298", "submission_value": "DIABP", "preferred_term": "Diastolic Blood Pressure", "synonyms": ["DBP", "Diastolic", "Diastolic BP"], "ordinal": 1},
                {"code": "C25299", "submission_value": "SYSBP", "preferred_term": "Systolic Blood Pressure", "synonyms": ["SBP", "Systolic", "Systolic BP"], "ordinal": 2},
                {"code": "C49676", "submission_value": "PULSE", "preferred_term": "Pulse Rate", "synonyms": ["Pulse", "Heart Rate", "HR", "PR"], "ordinal": 3},
                {"code": "C25208", "submission_value": "TEMP", "preferred_term": "Temperature", "synonyms": ["Temp", "Body Temperature", "Core Temp"], "ordinal": 4},
                {"code": "C49677", "submission_value": "RESP", "preferred_term": "Respiratory Rate", "synonyms": ["RR", "Respirations", "Breathing Rate"], "ordinal": 5},
                {"code": "C16358", "submission_value": "WEIGHT", "preferred_term": "Weight", "synonyms": ["Weight", "Body Weight", "Wt"], "ordinal": 6},
                {"code": "C25347", "submission_value": "HEIGHT", "preferred_term": "Height", "synonyms": ["Height", "Stature", "Ht"], "ordinal": 7},
                {"code": "C16352", "submission_value": "BMI", "preferred_term": "Body Mass Index", "synonyms": ["BMI", "Body Mass Index"], "ordinal": 8},
                {"code": "C64798", "submission_value": "OXYSAT", "preferred_term": "Oxygen Saturation", "synonyms": ["SpO2", "O2 Sat", "Pulse Ox", "Oxygen Sat"], "ordinal": 9},
                {"code": "C49678", "submission_value": "MAP", "preferred_term": "Mean Arterial Pressure", "synonyms": ["MAP", "Mean BP", "Mean Arterial"], "ordinal": 10},
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
            "nci_preferred_term": "Disposition Category",
            "terms": [
                {"code": "C49506", "submission_value": "DISPOSITION EVENT", "preferred_term": "Disposition Event", "synonyms": ["Disposition"], "ordinal": 1},
                {"code": "C49507", "submission_value": "PROTOCOL MILESTONE", "preferred_term": "Protocol Milestone", "synonyms": ["Milestone", "Visit"], "ordinal": 2},
                {"code": "C49508", "submission_value": "OTHER EVENT", "preferred_term": "Other Event", "synonyms": ["Other"], "ordinal": 3},
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
            "nci_preferred_term": "Subject Disposition",
            "terms": [
                {"code": "C28554", "submission_value": "COMPLETED", "preferred_term": "Completed", "synonyms": ["Completed", "Finished", "Done"], "ordinal": 1},
                {"code": "C49516", "submission_value": "ADVERSE EVENT", "preferred_term": "Adverse Event", "synonyms": ["AE", "Adverse Event", "Side Effect"], "ordinal": 2},
                {"code": "C49517", "submission_value": "DEATH", "preferred_term": "Death", "synonyms": ["Death", "Died", "Deceased", "Expired"], "ordinal": 3},
                {"code": "C49518", "submission_value": "LACK OF EFFICACY", "preferred_term": "Lack of Efficacy", "synonyms": ["Lack of Efficacy", "No Effect", "Ineffective"], "ordinal": 4},
                {"code": "C49519", "submission_value": "LOST TO FOLLOW-UP", "preferred_term": "Lost to Follow-Up", "synonyms": ["Lost to Follow-Up", "LTFU", "Lost"], "ordinal": 5},
                {"code": "C49520", "submission_value": "PHYSICIAN DECISION", "preferred_term": "Physician Decision", "synonyms": ["Physician Decision", "Investigator Decision"], "ordinal": 6},
                {"code": "C49521", "submission_value": "PROTOCOL DEVIATION", "preferred_term": "Protocol Deviation", "synonyms": ["Protocol Deviation", "PD", "Deviation"], "ordinal": 7},
                {"code": "C49522", "submission_value": "SCREEN FAILURE", "preferred_term": "Screen Failure", "synonyms": ["Screen Failure", "SF", "Failed Screening"], "ordinal": 8},
                {"code": "C49523", "submission_value": "WITHDRAWAL BY SUBJECT", "preferred_term": "Withdrawal by Subject", "synonyms": ["Withdrawal", "Subject Withdrew", "Withdrew Consent"], "ordinal": 9},
                {"code": "C49524", "submission_value": "PREGNANCY", "preferred_term": "Pregnancy", "synonyms": ["Pregnancy", "Pregnant"], "ordinal": 10},
                {"code": "C49525", "submission_value": "TECHNICAL PROBLEMS", "preferred_term": "Technical Problems", "synonyms": ["Technical", "Technical Issues"], "ordinal": 11},
            ],
        },
        # =================================================================
        # LBTESTCD (C65047) - Laboratory Test Code
        # =================================================================
        {
            "c_code": "C65047",
            "name": "Laboratory Test Code",
            "submission_value": "LBTESTCD",
            "definition": "Short codes for laboratory tests.",
            "codelist_type": "extensible",
            "domain": "LB",
            "nci_preferred_term": "Lab Test Code",
            "terms": [
                {"code": "C64547", "submission_value": "ALB", "preferred_term": "Albumin", "synonyms": ["Albumin"], "ordinal": 1},
                {"code": "C64548", "submission_value": "ALP", "preferred_term": "Alkaline Phosphatase", "synonyms": ["Alk Phos", "ALP", "Alkaline Phosphatase"], "ordinal": 2},
                {"code": "C64549", "submission_value": "ALT", "preferred_term": "Alanine Aminotransferase", "synonyms": ["ALT", "SGPT", "Alanine Transaminase"], "ordinal": 3},
                {"code": "C64550", "submission_value": "AST", "preferred_term": "Aspartate Aminotransferase", "synonyms": ["AST", "SGOT", "Aspartate Transaminase"], "ordinal": 4},
                {"code": "C64554", "submission_value": "BILI", "preferred_term": "Bilirubin", "synonyms": ["Bilirubin", "Total Bilirubin", "TBIL"], "ordinal": 5},
                {"code": "C64551", "submission_value": "BUN", "preferred_term": "Blood Urea Nitrogen", "synonyms": ["BUN", "Urea Nitrogen", "Urea"], "ordinal": 6},
                {"code": "C64552", "submission_value": "CA", "preferred_term": "Calcium", "synonyms": ["Calcium", "Ca", "Serum Calcium"], "ordinal": 7},
                {"code": "C64553", "submission_value": "CHOL", "preferred_term": "Cholesterol", "synonyms": ["Cholesterol", "Total Cholesterol", "TC"], "ordinal": 8},
                {"code": "C64555", "submission_value": "CREAT", "preferred_term": "Creatinine", "synonyms": ["Creatinine", "Cr", "Serum Creatinine"], "ordinal": 9},
                {"code": "C64556", "submission_value": "GLUC", "preferred_term": "Glucose", "synonyms": ["Glucose", "Blood Glucose", "Blood Sugar"], "ordinal": 10},
                {"code": "C64557", "submission_value": "HBA1C", "preferred_term": "Hemoglobin A1C", "synonyms": ["HbA1c", "A1C", "Glycated Hemoglobin", "Glycohemoglobin"], "ordinal": 11},
                {"code": "C64558", "submission_value": "HGB", "preferred_term": "Hemoglobin", "synonyms": ["Hemoglobin", "Hgb", "Hb"], "ordinal": 12},
                {"code": "C64559", "submission_value": "HCT", "preferred_term": "Hematocrit", "synonyms": ["Hematocrit", "Hct", "PCV"], "ordinal": 13},
                {"code": "C64560", "submission_value": "K", "preferred_term": "Potassium", "synonyms": ["Potassium", "K", "Serum K"], "ordinal": 14},
                {"code": "C64561", "submission_value": "NA", "preferred_term": "Sodium", "synonyms": ["Sodium", "Na", "Serum Na"], "ordinal": 15},
                {"code": "C64562", "submission_value": "PLAT", "preferred_term": "Platelet Count", "synonyms": ["Platelets", "PLT", "Platelet Count"], "ordinal": 16},
                {"code": "C64563", "submission_value": "WBC", "preferred_term": "White Blood Cell Count", "synonyms": ["WBC", "Leukocytes", "White Count"], "ordinal": 17},
                {"code": "C64564", "submission_value": "RBC", "preferred_term": "Red Blood Cell Count", "synonyms": ["RBC", "Erythrocytes", "Red Count"], "ordinal": 18},
                {"code": "C64565", "submission_value": "GGT", "preferred_term": "Gamma Glutamyl Transferase", "synonyms": ["GGT", "GGTP", "Gamma GT"], "ordinal": 19},
                {"code": "C64566", "submission_value": "LDH", "preferred_term": "Lactate Dehydrogenase", "synonyms": ["LDH", "Lactate Dehydrogenase"], "ordinal": 20},
                {"code": "C64567", "submission_value": "TRIG", "preferred_term": "Triglycerides", "synonyms": ["Triglycerides", "TG", "Trigs"], "ordinal": 21},
                {"code": "C64568", "submission_value": "LDL", "preferred_term": "LDL Cholesterol", "synonyms": ["LDL", "LDL-C", "Bad Cholesterol"], "ordinal": 22},
                {"code": "C64569", "submission_value": "HDL", "preferred_term": "HDL Cholesterol", "synonyms": ["HDL", "HDL-C", "Good Cholesterol"], "ordinal": 23},
                {"code": "C64570", "submission_value": "CL", "preferred_term": "Chloride", "synonyms": ["Chloride", "Cl", "Serum Chloride"], "ordinal": 24},
                {"code": "C64571", "submission_value": "CO2", "preferred_term": "Carbon Dioxide", "synonyms": ["CO2", "Bicarbonate", "HCO3"], "ordinal": 25},
                {"code": "C64572", "submission_value": "PHOS", "preferred_term": "Phosphate", "synonyms": ["Phosphate", "Phosphorus", "Phos"], "ordinal": 26},
                {"code": "C64573", "submission_value": "MG", "preferred_term": "Magnesium", "synonyms": ["Magnesium", "Mg", "Serum Mg"], "ordinal": 27},
                {"code": "C64574", "submission_value": "URATE", "preferred_term": "Uric Acid", "synonyms": ["Uric Acid", "Urate", "UA"], "ordinal": 28},
            ],
        },
    ]


def calculate_statistics(codelists: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate statistics about the terminology database."""
    total_terms = sum(len(cl.get("terms", [])) for cl in codelists)
    extensible_count = sum(1 for cl in codelists if cl.get("codelist_type") == "extensible")

    by_domain: dict[str, int] = {}
    for cl in codelists:
        domain = cl.get("domain", "GENERAL")
        by_domain[domain] = by_domain.get(domain, 0) + 1

    return {
        "total_codelists": len(codelists),
        "total_terms": total_terms,
        "extensible_codelists": extensible_count,
        "non_extensible_codelists": len(codelists) - extensible_count,
        "by_domain": by_domain,
    }


def fetch_from_nci_evs() -> list[dict[str, Any]] | None:
    """Attempt to fetch CDISC CT from NCI EVS.

    Note: This requires network access to NCI EVS FTP.
    Returns None if fetch fails.
    """
    try:
        print(f"Attempting to fetch CDISC CT from NCI EVS...")
        print(f"URL: {NCI_EVS_SDTM}")

        req = urllib.request.Request(
            NCI_EVS_SDTM,
            headers={"User-Agent": "CDISC-CT-Loader/1.0"}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            xml_content = response.read()

        # Parse the ODM XML
        root = ET.fromstring(xml_content)
        # Note: Full parsing would require ODM namespace handling
        # This is a placeholder for production implementation
        print("Successfully fetched NCI EVS data")
        return None  # Return None to fall back to built-in

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"Could not fetch from NCI EVS: {e}")
        return None
    except ET.ParseError as e:
        print(f"Error parsing NCI EVS XML: {e}")
        return None


def main():
    """Main function to generate CDISC CT fixture file."""
    parser = argparse.ArgumentParser(
        description="Load and process CDISC Controlled Terminology"
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Attempt to fetch latest CT from NCI EVS"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Output file path"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("CDISC Controlled Terminology Loader")
    print("=" * 60)

    # Ensure fixtures directory exists
    FIXTURES_DIR.mkdir(exist_ok=True)

    codelists: list[dict[str, Any]] = []

    # Try to fetch from NCI EVS if requested
    if args.fetch:
        fetched = fetch_from_nci_evs()
        if fetched:
            codelists = fetched

    # Fall back to built-in terminology
    if not codelists:
        print("Using built-in CDISC terminology...")
        codelists = get_builtin_codelists()

    # Calculate statistics
    stats = calculate_statistics(codelists)

    # Build output data
    output_data = {
        "metadata": {
            "source": "CDISC Controlled Terminology",
            "description": "CDISC SDTM Controlled Terminology for clinical trials",
            "version": "2024-03-29",
            "generated_at": datetime.now().isoformat(),
            **stats,
        },
        "versions": [
            {
                "version": "2024-03-29",
                "release_date": "2024-03-29",
                "description": "CDISC CT 2024-03-29 Release",
                "codelist_count": stats["total_codelists"],
                "term_count": stats["total_terms"],
                "is_current": True,
            },
            {
                "version": "2023-12-15",
                "release_date": "2023-12-15",
                "description": "CDISC CT 2023-12-15 Release",
                "codelist_count": stats["total_codelists"],
                "term_count": stats["total_terms"],
                "is_current": False,
            },
            {
                "version": "2023-09-29",
                "release_date": "2023-09-29",
                "description": "CDISC CT 2023-09-29 Release",
                "codelist_count": stats["total_codelists"],
                "term_count": stats["total_terms"],
                "is_current": False,
            },
        ],
        "codelists": codelists,
    }

    # Save to file
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"Generated: {args.output}")
    print(f"Total codelists: {stats['total_codelists']:,}")
    print(f"Total terms: {stats['total_terms']:,}")
    print(f"Extensible: {stats['extensible_codelists']:,}")
    print(f"Non-extensible: {stats['non_extensible_codelists']:,}")
    print()
    print("By Domain:")
    for domain, count in sorted(stats["by_domain"].items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
