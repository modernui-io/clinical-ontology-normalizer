"""SDTM Domain Templates.

Pre-built templates for common SDTM domains compliant with CDISC SDTM IG 3.3.
These templates provide standard variable definitions that can be used
as starting points for creating domain-specific mappings.

Supported domains:
- DM (Demographics)
- AE (Adverse Events)
- CM (Concomitant Medications)
- MH (Medical History)
- VS (Vital Signs)
- LB (Laboratory Test Results)
"""

from app.models.sdtm_mapping import (
    SDTMDataType,
    SDTMDomainClass,
    SDTMDomainSpec,
    SDTMVariable,
    SDTMVariableRole,
)


def _create_dm_template() -> SDTMDomainSpec:
    """Create Demographics (DM) domain template."""
    return SDTMDomainSpec(
        domain="DM",
        domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
        label="Demographics",
        structure="One record per subject",
        key_variables=["STUDYID", "USUBJID"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="SUBJID",
                label="Subject Identifier for the Study",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.TOPIC,
                core="Req",
            ),
            SDTMVariable(
                name="RFSTDTC",
                label="Subject Reference Start Date/Time",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="RFENDTC",
                label="Subject Reference End Date/Time",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="SITEID",
                label="Study Site Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="BRTHDTC",
                label="Date/Time of Birth",
                data_type=SDTMDataType.DATE,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Perm",
            ),
            SDTMVariable(
                name="AGE",
                label="Age",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AGEU",
                label="Age Units",
                data_type=SDTMDataType.CHAR,
                length=10,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="AGEU",
                core="Exp",
            ),
            SDTMVariable(
                name="SEX",
                label="Sex",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="SEX",
                core="Req",
            ),
            SDTMVariable(
                name="RACE",
                label="Race",
                data_type=SDTMDataType.CHAR,
                length=60,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="RACE",
                core="Exp",
            ),
            SDTMVariable(
                name="ETHNIC",
                label="Ethnicity",
                data_type=SDTMDataType.CHAR,
                length=60,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="ETHNIC",
                core="Exp",
            ),
            SDTMVariable(
                name="ARMCD",
                label="Planned Arm Code",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="ARM",
                label="Description of Planned Arm",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="COUNTRY",
                label="Country",
                data_type=SDTMDataType.CHAR,
                length=3,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="ISO 3166-1 Alpha-3",
                core="Req",
            ),
            SDTMVariable(
                name="DMDTC",
                label="Date/Time of Collection",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="DMDY",
                label="Study Day of Collection",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
        ],
    )


def _create_ae_template() -> SDTMDomainSpec:
    """Create Adverse Events (AE) domain template."""
    return SDTMDomainSpec(
        domain="AE",
        domain_class=SDTMDomainClass.EVENTS,
        label="Adverse Events",
        structure="One record per adverse event per subject",
        key_variables=["STUDYID", "USUBJID", "AESEQ"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="AESEQ",
                label="Sequence Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="AETERM",
                label="Reported Term for the Adverse Event",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.TOPIC,
                core="Req",
            ),
            SDTMVariable(
                name="AELLT",
                label="Lowest Level Term",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AELLTCD",
                label="Lowest Level Term Code",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AEDECOD",
                label="Dictionary-Derived Term",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="AEPTCD",
                label="Preferred Term Code",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AEHLT",
                label="High Level Term",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AEHLGT",
                label="High Level Group Term",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AEBODSYS",
                label="Body System or Organ Class",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AESEV",
                label="Severity/Intensity",
                data_type=SDTMDataType.CHAR,
                length=10,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="AESEV",
                core="Perm",
            ),
            SDTMVariable(
                name="AESER",
                label="Serious Event",
                data_type=SDTMDataType.CHAR,
                length=1,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="NY",
                core="Req",
            ),
            SDTMVariable(
                name="AEREL",
                label="Causality",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="AEACN",
                label="Action Taken with Study Treatment",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="ACN",
                core="Exp",
            ),
            SDTMVariable(
                name="AEOUT",
                label="Outcome of Adverse Event",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="OUT",
                core="Exp",
            ),
            SDTMVariable(
                name="AESTDTC",
                label="Start Date/Time of Adverse Event",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="AEENDTC",
                label="End Date/Time of Adverse Event",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="AESTDY",
                label="Study Day of Start of Adverse Event",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="AEENDY",
                label="Study Day of End of Adverse Event",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
        ],
    )


def _create_cm_template() -> SDTMDomainSpec:
    """Create Concomitant Medications (CM) domain template."""
    return SDTMDomainSpec(
        domain="CM",
        domain_class=SDTMDomainClass.INTERVENTIONS,
        label="Concomitant Medications",
        structure="One record per medication intervention per subject",
        key_variables=["STUDYID", "USUBJID", "CMSEQ"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="CMSEQ",
                label="Sequence Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="CMTRT",
                label="Reported Name of Drug, Med, or Therapy",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.TOPIC,
                core="Req",
            ),
            SDTMVariable(
                name="CMDECOD",
                label="Standardized Medication Name",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="CMCAT",
                label="Category for Medication",
                data_type=SDTMDataType.CHAR,
                length=100,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Perm",
            ),
            SDTMVariable(
                name="CMINDC",
                label="Indication",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="CMDOSE",
                label="Dose per Administration",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="CMDOSU",
                label="Dose Units",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="UNIT",
                core="Exp",
            ),
            SDTMVariable(
                name="CMDOSFRQ",
                label="Dosing Frequency per Interval",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="FREQ",
                core="Exp",
            ),
            SDTMVariable(
                name="CMROUTE",
                label="Route of Administration",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="ROUTE",
                core="Exp",
            ),
            SDTMVariable(
                name="CMSTDTC",
                label="Start Date/Time of Medication",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="CMENDTC",
                label="End Date/Time of Medication",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="CMSTDY",
                label="Study Day of Start of Medication",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="CMENDY",
                label="Study Day of End of Medication",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
        ],
    )


def _create_mh_template() -> SDTMDomainSpec:
    """Create Medical History (MH) domain template."""
    return SDTMDomainSpec(
        domain="MH",
        domain_class=SDTMDomainClass.EVENTS,
        label="Medical History",
        structure="One record per medical history event per subject",
        key_variables=["STUDYID", "USUBJID", "MHSEQ"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="MHSEQ",
                label="Sequence Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="MHTERM",
                label="Reported Term for the Medical History",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.TOPIC,
                core="Req",
            ),
            SDTMVariable(
                name="MHDECOD",
                label="Dictionary-Derived Term",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="MHCAT",
                label="Category for Medical History",
                data_type=SDTMDataType.CHAR,
                length=100,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Perm",
            ),
            SDTMVariable(
                name="MHBODSYS",
                label="Body System or Organ Class",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="MHSTDTC",
                label="Start Date/Time of Medical History Event",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="MHENDTC",
                label="End Date/Time of Medical History Event",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="MHENRF",
                label="End Relative to Reference Period",
                data_type=SDTMDataType.CHAR,
                length=10,
                role=SDTMVariableRole.TIMING,
                controlled_term="STENRF",
                core="Perm",
            ),
        ],
    )


def _create_vs_template() -> SDTMDomainSpec:
    """Create Vital Signs (VS) domain template."""
    return SDTMDomainSpec(
        domain="VS",
        domain_class=SDTMDomainClass.FINDINGS,
        label="Vital Signs",
        structure="One record per vital sign measurement per time point per subject",
        key_variables=["STUDYID", "USUBJID", "VSSEQ"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="VSSEQ",
                label="Sequence Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="VSTESTCD",
                label="Vital Signs Test Short Name",
                data_type=SDTMDataType.CHAR,
                length=8,
                role=SDTMVariableRole.TOPIC,
                controlled_term="VSTESTCD",
                core="Req",
            ),
            SDTMVariable(
                name="VSTEST",
                label="Vital Signs Test Name",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                controlled_term="VSTEST",
                core="Req",
            ),
            SDTMVariable(
                name="VSCAT",
                label="Category for Vital Signs",
                data_type=SDTMDataType.CHAR,
                length=100,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Perm",
            ),
            SDTMVariable(
                name="VSORRES",
                label="Result or Finding in Original Units",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="VSORRESU",
                label="Original Units",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="UNIT",
                core="Exp",
            ),
            SDTMVariable(
                name="VSSTRESC",
                label="Character Result/Finding in Std Format",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="VSSTRESN",
                label="Numeric Result/Finding in Standard Units",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="VSSTRESU",
                label="Standard Units",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="UNIT",
                core="Exp",
            ),
            SDTMVariable(
                name="VSPOS",
                label="Vital Signs Position of Subject",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="POSITION",
                core="Perm",
            ),
            SDTMVariable(
                name="VSLOC",
                label="Location of Vital Signs Measurement",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="LOC",
                core="Perm",
            ),
            SDTMVariable(
                name="VSDTC",
                label="Date/Time of Measurements",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="VSDY",
                label="Study Day of Vital Signs",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="VSTPT",
                label="Planned Time Point Name",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="VSTPTNUM",
                label="Planned Time Point Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="VISITNUM",
                label="Visit Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="VISIT",
                label="Visit Name",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
        ],
    )


def _create_lb_template() -> SDTMDomainSpec:
    """Create Laboratory Test Results (LB) domain template."""
    return SDTMDomainSpec(
        domain="LB",
        domain_class=SDTMDomainClass.FINDINGS,
        label="Laboratory Test Results",
        structure="One record per lab test per time point per subject",
        key_variables=["STUDYID", "USUBJID", "LBSEQ"],
        variables=[
            SDTMVariable(
                name="STUDYID",
                label="Study Identifier",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="DOMAIN",
                label="Domain Abbreviation",
                data_type=SDTMDataType.CHAR,
                length=2,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="USUBJID",
                label="Unique Subject Identifier",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="LBSEQ",
                label="Sequence Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.IDENTIFIER,
                core="Req",
            ),
            SDTMVariable(
                name="LBTESTCD",
                label="Lab Test or Examination Short Name",
                data_type=SDTMDataType.CHAR,
                length=8,
                role=SDTMVariableRole.TOPIC,
                controlled_term="LBTESTCD",
                core="Req",
            ),
            SDTMVariable(
                name="LBTEST",
                label="Lab Test or Examination Name",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.SYNONYM_QUALIFIER,
                controlled_term="LBTEST",
                core="Req",
            ),
            SDTMVariable(
                name="LBCAT",
                label="Category for Lab Test",
                data_type=SDTMDataType.CHAR,
                length=100,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBORRES",
                label="Result or Finding in Original Units",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBORRESU",
                label="Original Units",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="UNIT",
                core="Exp",
            ),
            SDTMVariable(
                name="LBORNRLO",
                label="Reference Range Lower Limit in Orig Unit",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBORNRHI",
                label="Reference Range Upper Limit in Orig Unit",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBSTRESC",
                label="Character Result/Finding in Std Format",
                data_type=SDTMDataType.CHAR,
                length=200,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBSTRESN",
                label="Numeric Result/Finding in Standard Units",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBSTRESU",
                label="Standard Units",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="UNIT",
                core="Exp",
            ),
            SDTMVariable(
                name="LBSTNRLO",
                label="Reference Range Lower Limit-Std Units",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBSTNRHI",
                label="Reference Range Upper Limit-Std Units",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                core="Exp",
            ),
            SDTMVariable(
                name="LBNRIND",
                label="Reference Range Indicator",
                data_type=SDTMDataType.CHAR,
                length=20,
                role=SDTMVariableRole.VARIABLE_QUALIFIER,
                controlled_term="NRIND",
                core="Exp",
            ),
            SDTMVariable(
                name="LBSPEC",
                label="Specimen Type",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="SPECTYPE",
                core="Perm",
            ),
            SDTMVariable(
                name="LBMETHOD",
                label="Method of Test or Examination",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="METHOD",
                core="Perm",
            ),
            SDTMVariable(
                name="LBBLFL",
                label="Baseline Flag",
                data_type=SDTMDataType.CHAR,
                length=1,
                role=SDTMVariableRole.RECORD_QUALIFIER,
                controlled_term="NY",
                core="Exp",
            ),
            SDTMVariable(
                name="LBDTC",
                label="Date/Time of Specimen Collection",
                data_type=SDTMDataType.DATETIME,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="LBDY",
                label="Study Day of Specimen Collection",
                data_type=SDTMDataType.INTEGER,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
            SDTMVariable(
                name="VISITNUM",
                label="Visit Number",
                data_type=SDTMDataType.NUM,
                role=SDTMVariableRole.TIMING,
                core="Exp",
            ),
            SDTMVariable(
                name="VISIT",
                label="Visit Name",
                data_type=SDTMDataType.CHAR,
                length=40,
                role=SDTMVariableRole.TIMING,
                core="Perm",
            ),
        ],
    )


# Template registry
_TEMPLATES: dict[str, SDTMDomainSpec] = {}


def _init_templates() -> None:
    """Initialize template registry."""
    global _TEMPLATES
    if not _TEMPLATES:
        _TEMPLATES = {
            "DM": _create_dm_template(),
            "AE": _create_ae_template(),
            "CM": _create_cm_template(),
            "MH": _create_mh_template(),
            "VS": _create_vs_template(),
            "LB": _create_lb_template(),
        }


def get_template(domain: str) -> SDTMDomainSpec | None:
    """Get a domain template by domain code.

    Args:
        domain: Two-letter domain code (DM, AE, CM, MH, VS, LB)

    Returns:
        Domain template or None if not found
    """
    _init_templates()
    template = _TEMPLATES.get(domain.upper())
    if template:
        # Return a fresh copy to avoid mutation
        return SDTMDomainSpec.from_dict(template.to_dict())
    return None


def list_templates() -> list[dict[str, str]]:
    """List all available templates.

    Returns:
        List of template info with domain, label, and class
    """
    _init_templates()
    return [
        {
            "domain": t.domain,
            "label": t.label,
            "domain_class": t.domain_class.value,
            "structure": t.structure,
            "variable_count": len(t.variables),
        }
        for t in _TEMPLATES.values()
    ]


def get_all_templates() -> list[SDTMDomainSpec]:
    """Get all domain templates.

    Returns:
        List of all domain templates
    """
    _init_templates()
    return [SDTMDomainSpec.from_dict(t.to_dict()) for t in _TEMPLATES.values()]
