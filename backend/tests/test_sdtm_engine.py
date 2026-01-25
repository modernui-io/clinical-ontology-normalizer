"""Tests for SDTM transformation engine.

Tests verify:
- Record transformation with various transformation types
- Domain-level transformation with batch processing
- Codelist lookups and validation
- Date conversion and formatting
- Expression evaluation
- Error handling for invalid transformations
"""

import pytest
from datetime import date, datetime

from app.services.sdtm_engine import (
    SDTMEngine,
    CodelistManager,
    RecordTransformResult,
    DomainTransformResult,
    get_sdtm_engine,
)
from app.models.sdtm_mapping import (
    SDTMDomainSpec,
    SDTMVariable,
    VariableMapping,
    VariableTransformation,
    TransformationType,
    SDTMDomainClass,
    SDTMDataType,
    SDTMVariableRole,
)


class TestCodelistManager:
    """Test codelist management."""

    def test_add_codelist(self):
        manager = CodelistManager()
        manager.add_codelist("CUSTOM", {
            "M": "MALE",
            "F": "FEMALE",
            "U": "UNKNOWN",
        })
        # Lookup uses lowercase keys
        assert manager.lookup("CUSTOM", "M") == "MALE"
        assert manager.lookup("CUSTOM", "F") == "FEMALE"

    def test_lookup_unknown_codelist(self):
        manager = CodelistManager()
        # Unknown codelist returns uppercased value
        result = manager.lookup("NONEXISTENT", "value")
        assert result == "VALUE"

    def test_lookup_missing_value(self):
        manager = CodelistManager()
        # SEX is a built-in codelist with male -> M mapping
        result = manager.lookup("SEX", "unknown_value")
        assert result is None  # Not found in mapping

    def test_lookup_builtin_sex_codelist(self):
        manager = CodelistManager()
        # Built-in SEX codelist maps to M/F/U
        assert manager.lookup("SEX", "male") == "M"
        assert manager.lookup("SEX", "female") == "F"
        assert manager.lookup("SEX", "m") == "M"
        assert manager.lookup("SEX", "f") == "F"

    def test_lookup_builtin_ny_codelist(self):
        manager = CodelistManager()
        # Built-in NY codelist
        assert manager.lookup("NY", "yes") == "Y"
        assert manager.lookup("NY", "no") == "N"
        assert manager.lookup("NY", "true") == "Y"
        assert manager.lookup("NY", "1") == "Y"
        assert manager.lookup("NY", "0") == "N"

    def test_lookup_none_value(self):
        manager = CodelistManager()
        result = manager.lookup("SEX", None)
        assert result is None


class TestVariableTransformations:
    """Test individual variable transformation types."""

    @pytest.fixture
    def engine(self):
        return SDTMEngine()

    def test_direct_transformation(self, engine):
        source = {"patient_name": "John Doe"}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="USUBJID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DIRECT,
                        source_columns=["patient_name"],
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["USUBJID"] == "John Doe"

    def test_constant_transformation(self, engine):
        source = {}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="STUDYID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CONSTANT,
                        constant_value="ABC123",
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["STUDYID"] == "ABC123"

    def test_concatenate_transformation(self, engine):
        source = {"site": "001", "subject": "0001"}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="USUBJID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CONCATENATE,
                        source_columns=["site", "subject"],
                        format_pattern="{0}-{1}",
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["USUBJID"] == "001-0001"

    def test_codelist_transformation(self, engine):
        source = {"gender": "male"}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="SEX",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CODELIST,
                        source_columns=["gender"],
                        codelist_id="SEX",
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["SEX"] == "M"

    def test_date_convert_transformation(self, engine):
        source = {"birth_date": "1990-05-15"}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="BRTHDTC", label="Birth Date", data_type=SDTMDataType.DATE),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="BRTHDTC",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DATE_CONVERT,
                        source_columns=["birth_date"],
                        format_pattern="%Y-%m-%d",
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert "1990-05-15" in str(result.sdtm_record.get("BRTHDTC", ""))

    def test_expression_transformation(self, engine):
        # The engine's expression evaluator supports simple conditional expressions
        source = {"status": "enrolled"}
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="ENRLFL", label="Enrolled Flag", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="ENRLFL",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.EXPRESSION,
                        format_pattern="'Y' if status == 'enrolled' else 'N'",
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["ENRLFL"] == "Y"

    def test_sequence_transformation(self, engine):
        source = {}
        spec = SDTMDomainSpec(
            domain="AE",
            variables=[
                SDTMVariable(name="AESEQ", label="Sequence", data_type=SDTMDataType.NUM),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="AESEQ",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.SEQUENCE,
                    ),
                ),
            ],
        )
        result = engine.transform_record(source, spec)
        assert result.success
        assert result.sdtm_record["AESEQ"] == 1


class TestRecordTransformation:
    """Test record-level transformation."""

    @pytest.fixture
    def engine(self):
        return SDTMEngine()

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            key_variables=["STUDYID", "USUBJID"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR, core="Req"),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="STUDYID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CONSTANT,
                        constant_value="STUDY001",
                    ),
                ),
                VariableMapping(
                    target_variable="USUBJID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DIRECT,
                        source_columns=["subject_id"],
                    ),
                ),
                VariableMapping(
                    target_variable="SEX",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CODELIST,
                        source_columns=["gender"],
                        codelist_id="SEX",
                    ),
                ),
            ],
        )

    def test_transform_record_success(self, engine, dm_spec):
        source = {"subject_id": "SUBJ001", "gender": "male"}
        result = engine.transform_record(source, dm_spec)

        assert result.success
        assert result.sdtm_record["STUDYID"] == "STUDY001"
        assert result.sdtm_record["DOMAIN"] == "DM"
        assert result.sdtm_record["USUBJID"] == "SUBJ001"
        assert result.sdtm_record["SEX"] == "M"
        assert len(result.errors) == 0

    def test_transform_record_preserves_row_number(self, engine, dm_spec):
        source = {"subject_id": "SUBJ001", "gender": "male"}
        result = engine.transform_record(source, dm_spec, row_number=5)

        assert result.success
        assert result.source_row == 5


class TestDomainTransformation:
    """Test domain-level batch transformation."""

    @pytest.fixture
    def engine(self):
        return SDTMEngine()

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            key_variables=["STUDYID", "USUBJID"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="STUDYID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CONSTANT,
                        constant_value="STUDY001",
                    ),
                ),
                VariableMapping(
                    target_variable="USUBJID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DIRECT,
                        source_columns=["id"],
                    ),
                ),
                VariableMapping(
                    target_variable="SEX",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CODELIST,
                        source_columns=["gender"],
                        codelist_id="SEX",
                    ),
                ),
            ],
        )

    def test_transform_domain_batch(self, engine, dm_spec):
        source_data = [
            {"id": "SUBJ001", "gender": "male"},
            {"id": "SUBJ002", "gender": "female"},
            {"id": "SUBJ003", "gender": "m"},
        ]
        result = engine.transform_domain(source_data, dm_spec)

        assert result.success
        assert result.record_count == 3
        assert result.success_count == 3
        assert result.error_count == 0
        assert len(result.records) == 3

    def test_transform_domain_empty(self, engine, dm_spec):
        result = engine.transform_domain([], dm_spec)
        assert result.success
        assert result.record_count == 0
        assert len(result.records) == 0


class TestEngineSingleton:
    """Test singleton pattern."""

    def test_get_sdtm_engine_singleton(self):
        engine1 = get_sdtm_engine()
        engine2 = get_sdtm_engine()
        assert engine1 is engine2

    def test_engine_has_codelist_manager(self):
        engine = get_sdtm_engine()
        assert hasattr(engine, "codelist_manager")
        assert isinstance(engine.codelist_manager, CodelistManager)


class TestMappingSpecProperty:
    """Test mapping spec property."""

    def test_mapping_spec_property(self):
        from app.models.sdtm_mapping import SDTMMappingSpec

        engine = SDTMEngine()
        assert engine.mapping_spec is None

        spec = SDTMMappingSpec(study_id="TEST", study_name="Test Study")
        engine.mapping_spec = spec
        assert engine.mapping_spec is spec

    def test_engine_with_initial_spec(self):
        from app.models.sdtm_mapping import SDTMMappingSpec

        spec = SDTMMappingSpec(study_id="TEST", study_name="Test Study")
        engine = SDTMEngine(mapping_spec=spec)
        assert engine.mapping_spec is spec


class TestDomainAutoAdd:
    """Test automatic DOMAIN variable addition."""

    def test_domain_auto_added(self):
        engine = SDTMEngine()
        spec = SDTMDomainSpec(
            domain="VS",
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="STUDYID",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.CONSTANT,
                        constant_value="STUDY001",
                    ),
                ),
            ],
        )
        result = engine.transform_record({}, spec)
        assert result.success
        assert result.sdtm_record["DOMAIN"] == "VS"


class TestConditionalMappings:
    """Test conditional variable mappings."""

    def test_conditional_mapping_applied(self):
        engine = SDTMEngine()
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="ARMCD", label="Arm Code", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="ARMCD",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DIRECT,
                        source_columns=["arm_code"],
                    ),
                    # Engine evaluates conditions using simple comparisons
                    condition="status == 'enrolled'",
                ),
            ],
        )
        source = {"arm_code": "ARM01", "status": "enrolled"}
        result = engine.transform_record(source, spec)
        assert result.sdtm_record.get("ARMCD") == "ARM01"

    def test_conditional_mapping_skipped(self):
        engine = SDTMEngine()
        spec = SDTMDomainSpec(
            domain="DM",
            variables=[
                SDTMVariable(name="ARMCD", label="Arm Code", data_type=SDTMDataType.CHAR),
            ],
            variable_mappings=[
                VariableMapping(
                    target_variable="ARMCD",
                    transformation=VariableTransformation(
                        transformation_type=TransformationType.DIRECT,
                        source_columns=["arm_code"],
                    ),
                    # Condition will be false when status != 'enrolled'
                    condition="status == 'enrolled'",
                ),
            ],
        )
        source = {"arm_code": "ARM01", "status": "screened"}
        result = engine.transform_record(source, spec)
        assert "ARMCD" not in result.sdtm_record


class TestRecordTransformResult:
    """Test RecordTransformResult structure."""

    def test_result_success_property(self):
        result = RecordTransformResult(
            source_row=0,
            sdtm_record={"STUDYID": "STUDY001"},
            errors=[],
        )
        assert result.success is True

        result_with_error = RecordTransformResult(
            source_row=0,
            sdtm_record={},
            errors=["Some error"],
        )
        assert result_with_error.success is False


class TestDomainTransformResult:
    """Test DomainTransformResult structure."""

    def test_result_success_property(self):
        result = DomainTransformResult(
            domain="DM",
            records=[{"STUDYID": "STUDY001"}],
            record_count=1,
            success_count=1,
            error_count=0,
        )
        assert result.success is True

        result_with_error = DomainTransformResult(
            domain="DM",
            records=[],
            record_count=1,
            success_count=0,
            error_count=1,
        )
        assert result_with_error.success is False
