"""Tests for SDTM dataset generator.

Tests verify:
- CSV file generation with correct structure
- XPT file generation (basic format)
- define.xml generation with proper ODM structure
- Package generation with multiple formats
- Error handling for invalid inputs
"""

import pytest
import tempfile
from pathlib import Path

from app.services.sdtm_generator import (
    SDTMGenerator,
    GenerationResult,
    DefineXmlResult,
    get_sdtm_generator,
)
from app.models.sdtm_mapping import (
    SDTMDomainSpec,
    SDTMVariable,
    SDTMMappingSpec,
    SDTMDomainClass,
    SDTMDataType,
    SDTMVariableRole,
)


class TestCSVGeneration:
    """Test CSV file generation."""

    @pytest.fixture
    def generator(self):
        return SDTMGenerator()

    @pytest.fixture
    def dm_spec(self):
        return SDTMDomainSpec(
            domain="DM",
            domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
            label="Demographics",
            structure="One record per subject",
            key_variables=["STUDYID", "USUBJID"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR),
                SDTMVariable(name="AGE", label="Age", data_type=SDTMDataType.NUM),
            ],
        )

    def test_generate_csv_basic(self, generator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M", "AGE": 45},
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ002", "SEX": "F", "AGE": 32},
        ]
        result = generator.generate_csv(dm_spec, records)

        assert result.success
        assert result.domain == "DM"
        assert result.format == "csv"
        assert result.record_count == 2
        assert result.file_content is not None

    def test_generate_csv_content_structure(self, generator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M", "AGE": 45},
        ]
        result = generator.generate_csv(dm_spec, records)

        csv_content = result.file_content.decode("utf-8")
        lines = csv_content.strip().split("\n")

        # Check header
        header = lines[0]
        assert "STUDYID" in header
        assert "DOMAIN" in header
        assert "USUBJID" in header
        assert "SEX" in header
        assert "AGE" in header

        # Check data row
        assert len(lines) == 2  # Header + 1 data row
        assert "STUDY001" in lines[1]
        assert "SUBJ001" in lines[1]

    def test_generate_csv_with_output_path(self, generator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M", "AGE": 45},
        ]

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            output_path = f.name

        result = generator.generate_csv(dm_spec, records, output_path=output_path)

        assert result.success
        assert result.file_path == output_path
        assert Path(output_path).exists()

        # Clean up
        Path(output_path).unlink()

    def test_generate_csv_empty_records(self, generator, dm_spec):
        result = generator.generate_csv(dm_spec, [])

        assert result.success
        assert result.record_count == 0
        # Should still have header
        csv_content = result.file_content.decode("utf-8")
        assert "STUDYID" in csv_content

    def test_generate_csv_ignores_extra_fields(self, generator, dm_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "DM", "USUBJID": "SUBJ001", "SEX": "M", "AGE": 45, "EXTRA": "ignored"},
        ]
        result = generator.generate_csv(dm_spec, records)

        assert result.success
        csv_content = result.file_content.decode("utf-8")
        assert "EXTRA" not in csv_content


class TestXPTGeneration:
    """Test SAS XPT transport file generation."""

    @pytest.fixture
    def generator(self):
        return SDTMGenerator()

    @pytest.fixture
    def vs_spec(self):
        return SDTMDomainSpec(
            domain="VS",
            domain_class=SDTMDomainClass.FINDINGS,
            label="Vital Signs",
            structure="One record per vital sign measurement per subject per visit",
            key_variables=["STUDYID", "USUBJID", "VSSEQ"],
            variables=[
                SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, length=20),
                SDTMVariable(name="DOMAIN", label="Domain", data_type=SDTMDataType.CHAR, length=2),
                SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, length=20),
                SDTMVariable(name="VSSEQ", label="Sequence", data_type=SDTMDataType.NUM),
                SDTMVariable(name="VSTESTCD", label="Test Code", data_type=SDTMDataType.CHAR, length=8),
                SDTMVariable(name="VSORRES", label="Result", data_type=SDTMDataType.CHAR, length=50),
            ],
        )

    def test_generate_xpt_basic(self, generator, vs_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 1, "VSTESTCD": "SYSBP", "VSORRES": "120"},
        ]
        result = generator.generate_xpt(vs_spec, records)

        assert result.success
        assert result.domain == "VS"
        assert result.format == "xpt"
        assert result.record_count == 1
        assert result.file_content is not None

    def test_generate_xpt_has_header_records(self, generator, vs_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 1, "VSTESTCD": "SYSBP", "VSORRES": "120"},
        ]
        result = generator.generate_xpt(vs_spec, records)

        xpt_content = result.file_content
        # XPT files should contain HEADER RECORD markers
        assert b"HEADER RECORD" in xpt_content
        # Should contain library reference
        assert b"LIBRARY" in xpt_content or b"SAS" in xpt_content

    def test_generate_xpt_with_output_path(self, generator, vs_spec):
        records = [
            {"STUDYID": "STUDY001", "DOMAIN": "VS", "USUBJID": "SUBJ001", "VSSEQ": 1, "VSTESTCD": "SYSBP", "VSORRES": "120"},
        ]

        with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as f:
            output_path = f.name

        result = generator.generate_xpt(vs_spec, records, output_path=output_path)

        assert result.success
        assert result.file_path == output_path
        assert Path(output_path).exists()
        assert Path(output_path).stat().st_size > 0

        # Clean up
        Path(output_path).unlink()

    def test_generate_xpt_empty_records(self, generator, vs_spec):
        result = generator.generate_xpt(vs_spec, [])

        assert result.success
        assert result.record_count == 0
        # Should still have header structure
        assert result.file_content is not None
        assert len(result.file_content) > 0


class TestDefineXMLGeneration:
    """Test define.xml metadata generation."""

    @pytest.fixture
    def generator(self):
        return SDTMGenerator()

    @pytest.fixture
    def mapping_spec(self):
        return SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
            domains=[
                SDTMDomainSpec(
                    domain="DM",
                    domain_class=SDTMDomainClass.SPECIAL_PURPOSE,
                    label="Demographics",
                    structure="One record per subject",
                    key_variables=["STUDYID", "USUBJID"],
                    variables=[
                        SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                        SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
                        SDTMVariable(name="SEX", label="Sex", data_type=SDTMDataType.CHAR, controlled_term="SEX"),
                    ],
                ),
                SDTMDomainSpec(
                    domain="AE",
                    domain_class=SDTMDomainClass.EVENTS,
                    label="Adverse Events",
                    structure="One record per adverse event per subject",
                    key_variables=["STUDYID", "USUBJID", "AESEQ"],
                    variables=[
                        SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR, core="Req"),
                        SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR, core="Req"),
                        SDTMVariable(name="AESEQ", label="Sequence", data_type=SDTMDataType.NUM, core="Req"),
                        SDTMVariable(name="AETERM", label="Reported Term", data_type=SDTMDataType.CHAR, core="Req"),
                    ],
                ),
            ],
        )

    def test_generate_define_xml_basic(self, generator, mapping_spec):
        result = generator.generate_define_xml(mapping_spec)

        assert result.success
        assert len(result.domains) == 2
        assert "DM" in result.domains
        assert "AE" in result.domains
        assert result.variable_count == 7  # 3 + 4 variables

    def test_generate_define_xml_structure(self, generator, mapping_spec):
        result = generator.generate_define_xml(mapping_spec)

        # Check XML structure
        assert '<?xml version="1.0"' in result.content
        assert "<ODM" in result.content
        assert "xmlns" in result.content
        assert "<Study" in result.content
        assert "<ItemGroupDef" in result.content
        assert "<ItemDef" in result.content

    def test_generate_define_xml_study_info(self, generator, mapping_spec):
        result = generator.generate_define_xml(mapping_spec)

        assert "STUDY001" in result.content
        assert "Test Study" in result.content
        assert "3.3" in result.content

    def test_generate_define_xml_item_groups(self, generator, mapping_spec):
        result = generator.generate_define_xml(mapping_spec)

        # Should have item groups for each domain
        assert 'Name="DM"' in result.content
        assert 'Name="AE"' in result.content
        assert "Demographics" in result.content
        assert "Adverse Events" in result.content

    def test_generate_define_xml_with_output_path(self, generator, mapping_spec):
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            output_path = f.name

        result = generator.generate_define_xml(mapping_spec, output_path=output_path)

        assert result.success
        assert Path(output_path).exists()

        content = Path(output_path).read_text()
        assert '<?xml version="1.0"' in content

        # Clean up
        Path(output_path).unlink()

    def test_generate_define_xml_no_spec(self, generator):
        result = generator.generate_define_xml(None)

        assert not result.success
        assert len(result.errors) > 0

    def test_generate_define_xml_uses_instance_spec(self, mapping_spec):
        generator = SDTMGenerator(mapping_spec=mapping_spec)
        result = generator.generate_define_xml()

        assert result.success
        assert "STUDY001" in result.content


class TestPackageGeneration:
    """Test complete package generation."""

    @pytest.fixture
    def generator(self):
        return SDTMGenerator()

    @pytest.fixture
    def mapping_spec(self):
        return SDTMMappingSpec(
            study_id="STUDY001",
            study_name="Test Study",
            sdtmig_version="3.3",
            domains=[
                SDTMDomainSpec(
                    domain="DM",
                    label="Demographics",
                    variables=[
                        SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR),
                        SDTMVariable(name="USUBJID", label="Subject ID", data_type=SDTMDataType.CHAR),
                    ],
                ),
            ],
        )

    def test_generate_package_csv_only(self, mapping_spec):
        generator = SDTMGenerator(mapping_spec=mapping_spec)

        domain_data = {
            "DM": [
                {"STUDYID": "STUDY001", "USUBJID": "SUBJ001"},
                {"STUDYID": "STUDY001", "USUBJID": "SUBJ002"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate_package(domain_data, tmpdir, formats=["csv"])

            assert result["success"]
            assert len(result["csv_files"]) == 1
            assert len(result["xpt_files"]) == 0
            assert Path(result["csv_files"][0]).exists()

    def test_generate_package_both_formats(self, mapping_spec):
        generator = SDTMGenerator(mapping_spec=mapping_spec)

        domain_data = {
            "DM": [
                {"STUDYID": "STUDY001", "USUBJID": "SUBJ001"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate_package(domain_data, tmpdir, formats=["csv", "xpt"])

            assert result["success"]
            assert len(result["csv_files"]) == 1
            assert len(result["xpt_files"]) == 1

    def test_generate_package_includes_define_xml(self, mapping_spec):
        generator = SDTMGenerator(mapping_spec=mapping_spec)

        domain_data = {
            "DM": [{"STUDYID": "STUDY001", "USUBJID": "SUBJ001"}]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate_package(domain_data, tmpdir)

            assert result["define_xml"] is not None
            assert "<?xml" in result["define_xml"]

    def test_generate_package_no_mapping_spec(self, generator):
        domain_data = {"DM": [{"STUDYID": "STUDY001"}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate_package(domain_data, tmpdir)

            assert not result["success"]
            assert len(result["errors"]) > 0

    def test_generate_package_unknown_domain(self, mapping_spec):
        generator = SDTMGenerator(mapping_spec=mapping_spec)

        domain_data = {
            "XX": [{"STUDYID": "STUDY001", "USUBJID": "SUBJ001"}]  # Unknown domain
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = generator.generate_package(domain_data, tmpdir)

            assert not result["success"]
            assert any("XX" in err for err in result["errors"])


class TestGeneratorSingleton:
    """Test singleton pattern."""

    def test_get_sdtm_generator_singleton(self):
        gen1 = get_sdtm_generator()
        gen2 = get_sdtm_generator()
        assert gen1 is gen2

    def test_generator_mapping_spec_property(self):
        generator = SDTMGenerator()
        assert generator.mapping_spec is None

        spec = SDTMMappingSpec(study_id="TEST", study_name="Test")
        generator.mapping_spec = spec
        assert generator.mapping_spec is spec


class TestOutputDirectory:
    """Test output directory handling."""

    def test_set_output_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "sdtm_output"
            generator = SDTMGenerator()
            generator.set_output_dir(new_dir)

            assert new_dir.exists()

    def test_generate_csv_uses_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = SDTMGenerator()
            generator.set_output_dir(tmpdir)

            spec = SDTMDomainSpec(
                domain="DM",
                variables=[SDTMVariable(name="STUDYID", label="Study ID", data_type=SDTMDataType.CHAR)],
            )
            records = [{"STUDYID": "STUDY001"}]

            result = generator.generate_csv(spec, records)

            assert result.success
            assert result.file_path is not None
            assert Path(result.file_path).parent == Path(tmpdir)
            assert "dm.csv" in result.file_path.lower()
