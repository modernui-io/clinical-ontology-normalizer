"""Tests for SDTM mapping specification models.

Tests verify:
- SDTMDomainSpec creation and serialization
- SDTMMappingSpec creation and management
- Variable and transformation definitions
- Serialization/deserialization roundtrip
"""

import pytest
from datetime import datetime, timezone

from app.models.sdtm_mapping import (
    SDTMDataType,
    SDTMDomainClass,
    SDTMDomainSpec,
    SDTMMappingSpec,
    SDTMVariable,
    SDTMVariableRole,
    TransformationType,
    VariableMapping,
    VariableTransformation,
)


class TestSDTMVariable:
    """Test SDTMVariable dataclass."""

    def test_create_basic_variable(self):
        var = SDTMVariable(
            name="USUBJID",
            label="Unique Subject Identifier",
            data_type=SDTMDataType.CHAR,
            length=40,
            role=SDTMVariableRole.IDENTIFIER,
            core="Req",
        )
        assert var.name == "USUBJID"
        assert var.label == "Unique Subject Identifier"
        assert var.data_type == SDTMDataType.CHAR
        assert var.length == 40
        assert var.role == SDTMVariableRole.IDENTIFIER
        assert var.core == "Req"

    def test_variable_defaults(self):
        var = SDTMVariable(name="TESTVAR", label="Test")
        assert var.data_type == SDTMDataType.CHAR
        assert var.length is None
        assert var.role == SDTMVariableRole.QUALIFIER
        assert var.core == "Perm"
        assert var.controlled_term is None
        assert var.comment is None

    def test_variable_to_dict(self):
        var = SDTMVariable(
            name="SEX",
            label="Sex",
            data_type=SDTMDataType.CHAR,
            length=2,
            role=SDTMVariableRole.RECORD_QUALIFIER,
            controlled_term="SEX",
            core="Req",
        )
        d = var.to_dict()
        assert d["name"] == "SEX"
        assert d["data_type"] == "Char"
        assert d["role"] == "Record Qualifier"
        assert d["controlled_term"] == "SEX"


class TestVariableTransformation:
    """Test VariableTransformation dataclass."""

    def test_direct_transformation(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.DIRECT,
            source_columns=["subject_id"],
        )
        assert trans.transformation_type == TransformationType.DIRECT
        assert trans.source_columns == ["subject_id"]

    def test_constant_transformation(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.CONSTANT,
            constant_value="DM",
        )
        assert trans.constant_value == "DM"

    def test_codelist_transformation(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.CODELIST,
            source_columns=["gender"],
            codelist_id="SEX",
        )
        assert trans.codelist_id == "SEX"

    def test_date_conversion_transformation(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.DATE_CONVERT,
            source_columns=["birth_date"],
            format_pattern="%Y-%m-%d",
        )
        assert trans.format_pattern == "%Y-%m-%d"

    def test_transformation_to_dict(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.CONCATENATE,
            source_columns=["study", "site", "subject"],
            format_pattern="{0}-{1}-{2}",
        )
        d = trans.to_dict()
        assert d["transformation_type"] == "concatenate"
        assert d["source_columns"] == ["study", "site", "subject"]


class TestVariableMapping:
    """Test VariableMapping dataclass."""

    def test_create_mapping(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.DIRECT,
            source_columns=["subject_id"],
        )
        mapping = VariableMapping(
            target_variable="SUBJID",
            transformation=trans,
            order=1,
        )
        assert mapping.target_variable == "SUBJID"
        assert mapping.transformation.transformation_type == TransformationType.DIRECT

    def test_conditional_mapping(self):
        trans = VariableTransformation(
            transformation_type=TransformationType.EXPRESSION,
            source_columns=["age", "age_unit"],
            format_pattern="age if age_unit == 'years' else age / 12",
        )
        mapping = VariableMapping(
            target_variable="AGE",
            transformation=trans,
            condition="age_unit in ('years', 'months')",
        )
        assert mapping.condition is not None


class TestSDTMDomainSpec:
    """Test SDTMDomainSpec dataclass."""

    def test_create_domain_spec(self):
        spec = SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            structure="One record per subject",
            key_variables=["STUDYID", "USUBJID"],
        )
        assert spec.domain == "DM"
        assert spec.domain_class == SDTMDomainClass.SPECIAL_PURPOSE
        assert spec.label == "Demographics"
        assert len(spec.key_variables) == 2

    def test_domain_spec_with_variables(self):
        variables = [
            SDTMVariable(name="STUDYID", label="Study Identifier", core="Req"),
            SDTMVariable(name="USUBJID", label="Unique Subject Identifier", core="Req"),
            SDTMVariable(name="SUBJID", label="Subject Identifier", core="Req"),
        ]
        spec = SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            variables=variables,
        )
        assert len(spec.variables) == 3

    def test_domain_spec_to_dict(self):
        spec = SDTMDomainSpec(
            domain="AE",
            domain_class=SDTMDomainClass.EVENTS,
            label="Adverse Events",
            version="1.0.0",
        )
        d = spec.to_dict()
        assert d["domain"] == "AE"
        assert d["domain_class"] == "events"
        assert d["label"] == "Adverse Events"
        assert "id" in d
        assert "created_at" in d

    def test_domain_spec_from_dict(self):
        data = {
            "domain": "CM",
            "domain_class": "interventions",
            "label": "Concomitant Medications",
            "structure": "One record per medication per subject",
            "key_variables": ["STUDYID", "USUBJID", "CMSEQ"],
            "variables": [
                {"name": "STUDYID", "label": "Study ID", "core": "Req"},
                {"name": "CMTRT", "label": "Treatment Name", "role": "Topic"},
            ],
        }
        spec = SDTMDomainSpec.from_dict(data)
        assert spec.domain == "CM"
        assert spec.domain_class == SDTMDomainClass.INTERVENTIONS
        assert len(spec.variables) == 2
        assert spec.variables[0].name == "STUDYID"

    def test_domain_spec_roundtrip(self):
        original = SDTMDomainSpec(
            domain="VS",
            domain_class=SDTMDomainClass.FINDINGS,
            label="Vital Signs",
            structure="One record per measurement per subject",
            key_variables=["STUDYID", "USUBJID", "VSSEQ"],
            variables=[
                SDTMVariable(
                    name="VSTESTCD",
                    label="Test Code",
                    role=SDTMVariableRole.TOPIC,
                    controlled_term="VSTESTCD",
                ),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="VSTESTCD",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CODELIST,
                        source_columns=["test_name"],
                        codelist_id="VSTESTCD",
                    ),
                ),
            ],
        )
        d = original.to_dict()
        restored = SDTMDomainSpec.from_dict(d)

        assert restored.domain == original.domain
        assert restored.domain_class == original.domain_class
        assert len(restored.variables) == len(original.variables)
        assert len(restored.variable_mappings) == len(original.variable_mappings)


class TestSDTMMappingSpec:
    """Test SDTMMappingSpec dataclass."""

    def test_create_mapping_spec(self):
        spec = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
        )
        assert spec.study_id == "STUDY001"
        assert spec.sdtmig_version == "3.3"
        assert spec.status == "draft"

    def test_mapping_spec_with_domains(self):
        dm = SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
        )
        ae = SDTMDomainSpec(
            domain="AE",
            domain_class=SDTMDomainClass.EVENTS,
            label="Adverse Events",
        )
        spec = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            domains=[dm, ae],
        )
        assert len(spec.domains) == 2

    def test_get_domain(self):
        dm = SDTMDomainSpec(domain="DM", label="Demographics")
        ae = SDTMDomainSpec(domain="AE", label="Adverse Events")
        spec = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            domains=[dm, ae],
        )
        assert spec.get_domain("DM") is not None
        assert spec.get_domain("DM").label == "Demographics"
        assert spec.get_domain("XX") is None

    def test_add_domain(self):
        spec = SDTMMappingSpec(study_id="STUDY001", study_name="Test")
        dm = SDTMDomainSpec(domain="DM", label="Demographics")
        spec.add_domain(dm)
        assert len(spec.domains) == 1

        # Adding same domain replaces
        dm2 = SDTMDomainSpec(domain="DM", label="Demographics v2")
        spec.add_domain(dm2)
        assert len(spec.domains) == 1
        assert spec.get_domain("DM").label == "Demographics v2"

    def test_mapping_spec_to_dict(self):
        spec = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
            global_variables={"STUDYID": "STUDY001"},
            status="active",
        )
        d = spec.to_dict()
        assert d["study_id"] == "STUDY001"
        assert d["global_variables"]["STUDYID"] == "STUDY001"
        assert d["status"] == "active"

    def test_mapping_spec_roundtrip(self):
        original = SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
            domains=[
                SDTMDomainSpec(
                    domain="DM",
                    domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
                    label="Demographics",
                    variables=[
                        SDTMVariable(name="USUBJID", label="Subject ID"),
                    ],
                ),
            ],
            global_variables={"STUDYID": "STUDY001"},
        )
        d = original.to_dict()
        restored = SDTMMappingSpec.from_dict(d)

        assert restored.study_id == original.study_id
        assert len(restored.domains) == 1
        assert restored.domains[0].domain == "DM"


class TestEnums:
    """Test enum values."""

    def test_domain_classes(self):
        assert SDTMDomainClass.SPECIAL_PURPOSE.value == "special_purpose"
        assert SDTMDomainClass.EVENTS.value == "events"
        assert SDTMDomainClass.FINDINGS.value == "findings"
        assert SDTMDomainClass.INTERVENTIONS.value == "interventions"

    def test_variable_roles(self):
        assert SDTMVariableRole.IDENTIFIER.value == "Identifier"
        assert SDTMVariableRole.TOPIC.value == "Topic"
        assert SDTMVariableRole.TIMING.value == "Timing"

    def test_data_types(self):
        assert SDTMDataType.CHAR.value == "Char"
        assert SDTMDataType.NUM.value == "Num"
        assert SDTMDataType.DATETIME.value == "datetime"

    def test_transformation_types(self):
        assert TransformationType.DIRECT.value == "direct"
        assert TransformationType.CODELIST.value == "codelist"
        assert TransformationType.EXPRESSION.value == "expression"
