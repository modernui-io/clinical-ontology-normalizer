"""Tests for SDTM domain templates.

Tests verify:
- Templates exist for all required domains (DM, AE, CM, MH, VS, LB)
- Templates have correct structure and required variables
- Template listing and retrieval work correctly
- Templates follow CDISC SDTMIG 3.3 specifications
"""

import pytest

from app.services.sdtm_templates import (
    get_template,
    get_all_templates,
    list_templates,
)
from app.models.sdtm_mapping import (
    SDTMDomainClass,
    SDTMDataType,
    SDTMVariableRole,
)


class TestTemplateRegistry:
    """Test template registry functions."""

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) >= 6  # DM, AE, CM, MH, VS, LB

        domains = [t["domain"] for t in templates]
        assert "DM" in domains
        assert "AE" in domains
        assert "CM" in domains
        assert "MH" in domains
        assert "VS" in domains
        assert "LB" in domains

    def test_list_templates_has_metadata(self):
        templates = list_templates()
        for t in templates:
            assert "domain" in t
            assert "label" in t
            assert "domain_class" in t
            assert "structure" in t
            assert "variable_count" in t
            assert t["variable_count"] > 0

    def test_get_all_templates(self):
        templates = get_all_templates()
        assert len(templates) >= 6

        for template in templates:
            assert template.domain
            assert template.label
            assert len(template.variables) > 0

    def test_get_template_returns_copy(self):
        """Verify get_template returns independent copies that can be modified."""
        t1 = get_template("DM")
        t2 = get_template("DM")
        # Modify t1 and verify t2 is unaffected
        t1.label = "Modified"
        assert t2.label == "Demographics"  # Original unchanged

    def test_get_template_not_found(self):
        result = get_template("XX")
        assert result is None

    def test_get_template_case_insensitive(self):
        dm_upper = get_template("DM")
        dm_lower = get_template("dm")
        assert dm_upper is not None
        assert dm_lower is not None
        assert dm_upper.domain == dm_lower.domain


class TestDMTemplate:
    """Test Demographics (DM) domain template."""

    def test_dm_domain_metadata(self):
        dm = get_template("DM")
        assert dm.domain == "DM"
        assert dm.domain_class == SDTMDomainClass.SPECIAL_PURPOSE
        assert dm.label == "Demographics"
        assert "One record per subject" in dm.structure

    def test_dm_key_variables(self):
        dm = get_template("DM")
        assert "STUDYID" in dm.key_variables
        assert "USUBJID" in dm.key_variables

    def test_dm_required_variables(self):
        dm = get_template("DM")
        var_names = [v.name for v in dm.variables]

        # Required identifier variables
        assert "STUDYID" in var_names
        assert "DOMAIN" in var_names
        assert "USUBJID" in var_names
        assert "SUBJID" in var_names
        assert "SITEID" in var_names

        # Required demographic variables
        assert "SEX" in var_names
        assert "ARMCD" in var_names
        assert "ARM" in var_names
        assert "COUNTRY" in var_names

    def test_dm_expected_variables(self):
        dm = get_template("DM")
        var_names = [v.name for v in dm.variables]

        # Expected timing variables
        assert "RFSTDTC" in var_names
        assert "RFENDTC" in var_names

        # Expected qualifier variables
        assert "AGE" in var_names
        assert "AGEU" in var_names
        assert "RACE" in var_names
        assert "ETHNIC" in var_names

    def test_dm_variable_properties(self):
        dm = get_template("DM")
        var_map = {v.name: v for v in dm.variables}

        # Check SEX variable
        sex = var_map["SEX"]
        assert sex.data_type == SDTMDataType.CHAR
        assert sex.role == SDTMVariableRole.RECORD_QUALIFIER
        assert sex.controlled_term == "SEX"
        assert sex.core == "Req"

        # Check USUBJID variable
        usubjid = var_map["USUBJID"]
        assert usubjid.role == SDTMVariableRole.IDENTIFIER
        assert usubjid.core == "Req"


class TestAETemplate:
    """Test Adverse Events (AE) domain template."""

    def test_ae_domain_metadata(self):
        ae = get_template("AE")
        assert ae.domain == "AE"
        assert ae.domain_class == SDTMDomainClass.EVENTS
        assert ae.label == "Adverse Events"

    def test_ae_key_variables(self):
        ae = get_template("AE")
        assert "STUDYID" in ae.key_variables
        assert "USUBJID" in ae.key_variables
        assert "AESEQ" in ae.key_variables

    def test_ae_required_variables(self):
        ae = get_template("AE")
        var_names = [v.name for v in ae.variables]

        assert "AETERM" in var_names
        assert "AEDECOD" in var_names
        assert "AESER" in var_names
        assert "AESEQ" in var_names

    def test_ae_coding_variables(self):
        ae = get_template("AE")
        var_names = [v.name for v in ae.variables]

        # MedDRA coding variables
        assert "AELLT" in var_names
        assert "AELLTCD" in var_names
        assert "AEPTCD" in var_names
        assert "AEHLT" in var_names
        assert "AEHLGT" in var_names
        assert "AEBODSYS" in var_names

    def test_ae_timing_variables(self):
        ae = get_template("AE")
        var_names = [v.name for v in ae.variables]

        assert "AESTDTC" in var_names
        assert "AEENDTC" in var_names
        assert "AESTDY" in var_names
        assert "AEENDY" in var_names


class TestCMTemplate:
    """Test Concomitant Medications (CM) domain template."""

    def test_cm_domain_metadata(self):
        cm = get_template("CM")
        assert cm.domain == "CM"
        assert cm.domain_class == SDTMDomainClass.INTERVENTIONS
        assert cm.label == "Concomitant Medications"

    def test_cm_required_variables(self):
        cm = get_template("CM")
        var_names = [v.name for v in cm.variables]

        assert "CMTRT" in var_names
        assert "CMSEQ" in var_names

    def test_cm_dosing_variables(self):
        cm = get_template("CM")
        var_names = [v.name for v in cm.variables]

        assert "CMDOSE" in var_names
        assert "CMDOSU" in var_names
        assert "CMDOSFRQ" in var_names
        assert "CMROUTE" in var_names


class TestMHTemplate:
    """Test Medical History (MH) domain template."""

    def test_mh_domain_metadata(self):
        mh = get_template("MH")
        assert mh.domain == "MH"
        assert mh.domain_class == SDTMDomainClass.EVENTS
        assert mh.label == "Medical History"

    def test_mh_required_variables(self):
        mh = get_template("MH")
        var_names = [v.name for v in mh.variables]

        assert "MHTERM" in var_names
        assert "MHSEQ" in var_names


class TestVSTemplate:
    """Test Vital Signs (VS) domain template."""

    def test_vs_domain_metadata(self):
        vs = get_template("VS")
        assert vs.domain == "VS"
        assert vs.domain_class == SDTMDomainClass.FINDINGS
        assert vs.label == "Vital Signs"

    def test_vs_key_variables(self):
        vs = get_template("VS")
        assert "VSSEQ" in vs.key_variables

    def test_vs_topic_variables(self):
        vs = get_template("VS")
        var_map = {v.name: v for v in vs.variables}

        assert "VSTESTCD" in var_map
        vstestcd = var_map["VSTESTCD"]
        assert vstestcd.role == SDTMVariableRole.TOPIC
        assert vstestcd.controlled_term == "VSTESTCD"

    def test_vs_result_variables(self):
        vs = get_template("VS")
        var_names = [v.name for v in vs.variables]

        assert "VSORRES" in var_names
        assert "VSORRESU" in var_names
        assert "VSSTRESC" in var_names
        assert "VSSTRESN" in var_names
        assert "VSSTRESU" in var_names


class TestLBTemplate:
    """Test Laboratory Test Results (LB) domain template."""

    def test_lb_domain_metadata(self):
        lb = get_template("LB")
        assert lb.domain == "LB"
        assert lb.domain_class == SDTMDomainClass.FINDINGS
        assert lb.label == "Laboratory Test Results"

    def test_lb_topic_variables(self):
        lb = get_template("LB")
        var_map = {v.name: v for v in lb.variables}

        assert "LBTESTCD" in var_map
        lbtestcd = var_map["LBTESTCD"]
        assert lbtestcd.role == SDTMVariableRole.TOPIC
        assert lbtestcd.controlled_term == "LBTESTCD"

    def test_lb_result_variables(self):
        lb = get_template("LB")
        var_names = [v.name for v in lb.variables]

        assert "LBORRES" in var_names
        assert "LBORRESU" in var_names
        assert "LBSTRESC" in var_names
        assert "LBSTRESN" in var_names
        assert "LBSTRESU" in var_names

    def test_lb_reference_range_variables(self):
        lb = get_template("LB")
        var_names = [v.name for v in lb.variables]

        assert "LBORNRLO" in var_names
        assert "LBORNRHI" in var_names
        assert "LBSTNRLO" in var_names
        assert "LBSTNRHI" in var_names
        assert "LBNRIND" in var_names

    def test_lb_specimen_variables(self):
        lb = get_template("LB")
        var_names = [v.name for v in lb.variables]

        assert "LBSPEC" in var_names
        assert "LBMETHOD" in var_names


class TestTemplateConsistency:
    """Test consistency across all templates."""

    def test_all_templates_have_identifiers(self):
        """All templates should have standard identifier variables."""
        for template in get_all_templates():
            var_names = [v.name for v in template.variables]
            assert "STUDYID" in var_names, f"{template.domain} missing STUDYID"
            assert "DOMAIN" in var_names, f"{template.domain} missing DOMAIN"
            assert "USUBJID" in var_names, f"{template.domain} missing USUBJID"

    def test_all_templates_have_sequence(self):
        """All templates except DM should have sequence variable."""
        for template in get_all_templates():
            if template.domain == "DM":
                continue
            var_names = [v.name for v in template.variables]
            seq_var = f"{template.domain}SEQ"
            assert seq_var in var_names, f"{template.domain} missing {seq_var}"

    def test_all_templates_serializable(self):
        """All templates should serialize and deserialize correctly."""
        from app.models.sdtm_mapping import SDTMDomainSpec

        for template in get_all_templates():
            d = template.to_dict()
            restored = SDTMDomainSpec.from_dict(d)
            assert restored.domain == template.domain
            assert len(restored.variables) == len(template.variables)
