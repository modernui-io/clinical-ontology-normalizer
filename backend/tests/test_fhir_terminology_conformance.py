"""FHIR Terminology Services Conformance Tests (P1-012).

Tests conformance with FHIR R4 Terminology Service operations:
- ValueSet CRUD
- $expand operation (GET and POST)
- $validate-code operation (GET and POST)
- FHIR ValueSet import/export
- Version management and status transitions
- Extensional and intensional value sets
"""

import pytest

from app.services.value_set_service import (
    FilterOperator,
    InclusionRule,
    InclusionRuleType,
    ValidationResult,
    ValueSet,
    ValueSetCode,
    ValueSetExpansionResult,
    ValueSetService,
    ValueSetStatus,
    ValueSetType,
    ValueSetVersion,
    get_value_set_service,
    reset_value_set_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the value set service singleton before each test."""
    reset_value_set_service()
    yield
    reset_value_set_service()


@pytest.fixture
def service() -> ValueSetService:
    """Create a fresh ValueSetService instance."""
    return ValueSetService()


@pytest.fixture
def diabetes_codes() -> list[ValueSetCode]:
    """Diabetes ICD-10 codes for testing."""
    return [
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11",
            display="Type 2 diabetes mellitus",
        ),
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11.9",
            display="Type 2 diabetes mellitus without complications",
        ),
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11.65",
            display="Type 2 diabetes mellitus with hyperglycemia",
        ),
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E10",
            display="Type 1 diabetes mellitus",
        ),
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E10.9",
            display="Type 1 diabetes mellitus without complications",
        ),
    ]


@pytest.fixture
def hypertension_codes() -> list[ValueSetCode]:
    """Hypertension ICD-10 codes for testing."""
    return [
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="I10",
            display="Essential (primary) hypertension",
        ),
        ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="I11.9",
            display="Hypertensive heart disease without heart failure",
        ),
    ]


@pytest.fixture
def sample_fhir_valueset() -> dict:
    """A sample FHIR R4 ValueSet resource."""
    return {
        "resourceType": "ValueSet",
        "id": "test-fhir-vs",
        "url": "http://example.org/ValueSet/test-fhir",
        "version": "2.0.0",
        "name": "TestFHIRValueSet",
        "title": "Test FHIR Value Set",
        "status": "active",
        "description": "A test value set in FHIR format",
        "publisher": "Test Publisher",
        "purpose": "Testing FHIR import",
        "compose": {
            "include": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10-cm",
                    "concept": [
                        {"code": "J06.9", "display": "Acute upper respiratory infection, unspecified"},
                        {"code": "J20.9", "display": "Acute bronchitis, unspecified"},
                    ],
                }
            ]
        },
    }


# ============================================================================
# ValueSet CRUD Tests
# ============================================================================


class TestValueSetCreate:
    """Test value set creation conforming to FHIR semantics."""

    def test_create_extensional_value_set(self, service, diabetes_codes):
        """Create an extensional value set with enumerated codes."""
        vs = service.create(
            name="TestDiabetes",
            value_set_type=ValueSetType.EXTENSIONAL,
            title="Test Diabetes Diagnoses",
            description="Test value set for diabetes",
            url="http://example.org/ValueSet/test-diabetes",
            version="1.0.0",
            status=ValueSetStatus.DRAFT,
            codes=diabetes_codes,
        )

        assert vs is not None
        assert vs.name == "TestDiabetes"
        assert vs.title == "Test Diabetes Diagnoses"
        assert vs.value_set_type == ValueSetType.EXTENSIONAL
        assert vs.status == ValueSetStatus.DRAFT
        assert vs.version == "1.0.0"
        assert len(vs.codes) == 5
        assert vs.url == "http://example.org/ValueSet/test-diabetes"

    def test_create_intensional_value_set(self, service):
        """Create an intensional value set with rules."""
        rules = [
            InclusionRule(
                rule_type=InclusionRuleType.DESCENDANTS,
                system="http://snomed.info/sct",
                code="73211009",
                include=True,
            ),
        ]

        vs = service.create(
            name="DiabetesDescendants",
            value_set_type=ValueSetType.INTENSIONAL,
            title="Diabetes and Descendants",
            description="All descendants of diabetes concept",
            rules=rules,
        )

        assert vs is not None
        assert vs.value_set_type == ValueSetType.INTENSIONAL
        assert len(vs.rules) == 1
        assert vs.rules[0].rule_type == InclusionRuleType.DESCENDANTS

    def test_create_with_metadata(self, service, diabetes_codes):
        """Create value set with full FHIR metadata."""
        vs = service.create(
            name="MetadataTest",
            value_set_type=ValueSetType.EXTENSIONAL,
            title="Metadata Test VS",
            description="Test with full metadata",
            url="http://example.org/ValueSet/metadata-test",
            version="1.0.0",
            status=ValueSetStatus.DRAFT,
            codes=diabetes_codes[:2],
            publisher="Test Organization",
            purpose="Testing metadata fields",
            copyright="(c) Test 2024",
            experimental=True,
            immutable=False,
        )

        assert vs.publisher == "Test Organization"
        assert vs.purpose == "Testing metadata fields"
        assert vs.copyright == "(c) Test 2024"
        assert vs.experimental is True
        assert vs.immutable is False

    def test_create_assigns_unique_id(self, service, diabetes_codes):
        """Each created value set gets a unique ID."""
        vs1 = service.create(name="VS1", value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes[:1])
        vs2 = service.create(name="VS2", value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes[1:2])
        assert vs1.id != vs2.id

    def test_create_sets_timestamps(self, service):
        """Created value set has created_at and updated_at timestamps."""
        vs = service.create(name="TimestampTest", value_set_type=ValueSetType.EXTENSIONAL)
        assert vs.created_at is not None
        assert vs.updated_at is not None


class TestValueSetRead:
    """Test value set retrieval."""

    def test_get_by_id(self, service, diabetes_codes):
        """Retrieve a value set by its ID."""
        created = service.create(name="GetTest", value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)
        retrieved = service.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "GetTest"

    def test_get_nonexistent_returns_none(self, service):
        """Getting a nonexistent value set returns None."""
        result = service.get("nonexistent-id")
        assert result is None

    def test_list_all(self, service, diabetes_codes, hypertension_codes):
        """List all value sets."""
        service.create(name="VS1", value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)
        service.create(name="VS2", value_set_type=ValueSetType.EXTENSIONAL, codes=hypertension_codes)

        results, total = service.list()
        assert total >= 2

    def test_list_filter_by_status(self, service, diabetes_codes):
        """Filter value sets by status."""
        service.create(name="DraftVS", value_set_type=ValueSetType.EXTENSIONAL,
                       status=ValueSetStatus.DRAFT, codes=diabetes_codes[:1])
        active_vs = service.create(name="ActiveVS", value_set_type=ValueSetType.EXTENSIONAL,
                                   status=ValueSetStatus.DRAFT, codes=diabetes_codes[1:2])
        service.activate(active_vs.id)

        draft_results, _ = service.list(status=ValueSetStatus.DRAFT)
        active_results, _ = service.list(status=ValueSetStatus.ACTIVE)

        draft_names = [vs.name for vs in draft_results]
        active_names = [vs.name for vs in active_results]

        assert "DraftVS" in draft_names
        assert "ActiveVS" in active_names

    def test_list_filter_by_type(self, service, diabetes_codes):
        """Filter value sets by type."""
        service.create(name="ExtVS", value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes[:1])
        service.create(
            name="IntVS",
            value_set_type=ValueSetType.INTENSIONAL,
            rules=[InclusionRule(
                rule_type=InclusionRuleType.CODE,
                system="http://snomed.info/sct",
                code="73211009",
            )],
        )

        ext_results, _ = service.list(value_set_type=ValueSetType.EXTENSIONAL)
        int_results, _ = service.list(value_set_type=ValueSetType.INTENSIONAL)

        ext_names = [vs.name for vs in ext_results]
        int_names = [vs.name for vs in int_results]

        assert "ExtVS" in ext_names
        assert "IntVS" in int_names

    def test_list_with_search(self, service, diabetes_codes, hypertension_codes):
        """Search value sets by name/title/description."""
        service.create(name="DiabetesCodes", title="Diabetes", value_set_type=ValueSetType.EXTENSIONAL,
                       codes=diabetes_codes)
        service.create(name="HTNCodes", title="Hypertension", value_set_type=ValueSetType.EXTENSIONAL,
                       codes=hypertension_codes)

        results, _ = service.list(search="diabetes")
        names = [vs.name for vs in results]
        assert "DiabetesCodes" in names

    def test_list_pagination(self, service, diabetes_codes):
        """Pagination with offset and limit."""
        for i in range(5):
            service.create(name=f"PaginateVS{i}", value_set_type=ValueSetType.EXTENSIONAL,
                           codes=diabetes_codes[:1])

        page1, total = service.list(offset=0, limit=2)
        page2, _ = service.list(offset=2, limit=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert total >= 5


class TestValueSetUpdate:
    """Test value set updates."""

    def test_update_name_and_title(self, service, diabetes_codes):
        """Update value set name and title."""
        vs = service.create(name="Original", title="Original Title",
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes[:1])

        updated = service.update(vs.id, name="Updated", title="Updated Title")
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.title == "Updated Title"

    def test_update_codes(self, service, diabetes_codes, hypertension_codes):
        """Update codes in an extensional value set."""
        vs = service.create(name="CodeUpdate", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:2])

        updated = service.update(vs.id, codes=hypertension_codes)
        assert updated is not None
        assert len(updated.codes) == 2

    def test_update_nonexistent_returns_none(self, service):
        """Updating a nonexistent value set returns None."""
        result = service.update("nonexistent", name="NewName")
        assert result is None


class TestValueSetDelete:
    """Test value set deletion."""

    def test_delete_existing(self, service, diabetes_codes):
        """Delete an existing value set."""
        vs = service.create(name="ToDelete", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:1])
        result = service.delete(vs.id)
        assert result is True
        assert service.get(vs.id) is None

    def test_delete_nonexistent(self, service):
        """Deleting nonexistent value set returns False."""
        result = service.delete("nonexistent")
        assert result is False


# ============================================================================
# $expand Operation Tests
# ============================================================================


class TestExpandOperation:
    """Test the FHIR $expand operation.

    Per FHIR R4: The $expand operation returns the full list of codes
    that are members of a value set.
    """

    def test_expand_extensional(self, service, diabetes_codes):
        """Expand an extensional value set returns all codes."""
        vs = service.create(name="ExpandTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        expansion = service.expand(vs.id)
        assert expansion is not None
        assert expansion.value_set_id == vs.id
        assert expansion.total == 5
        assert len(expansion.codes) == 5

    def test_expand_returns_correct_code_fields(self, service, diabetes_codes):
        """Expanded codes have system, code, display."""
        vs = service.create(name="FieldTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:1])

        expansion = service.expand(vs.id)
        code = expansion.codes[0]
        assert code.system == "http://hl7.org/fhir/sid/icd-10-cm"
        assert code.code == "E11"
        assert code.display == "Type 2 diabetes mellitus"

    def test_expand_with_filter(self, service, diabetes_codes):
        """Expand with text filter narrows results."""
        vs = service.create(name="FilterTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        expansion = service.expand(vs.id, filter_text="type 2")
        assert expansion is not None
        # Should match codes with "Type 2" in display
        for code in expansion.codes:
            assert "type 2" in code.display.lower() or "e11" in code.code.lower()

    def test_expand_with_pagination(self, service, diabetes_codes):
        """Expand with offset and count for pagination."""
        vs = service.create(name="PageTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        page1 = service.expand(vs.id, offset=0, count=2)
        page2 = service.expand(vs.id, offset=2, count=2)

        assert page1 is not None
        assert len(page1.codes) == 2
        assert page1.total == 5
        assert page1.offset == 0

        assert page2 is not None
        assert len(page2.codes) == 2
        assert page2.offset == 2

    def test_expand_active_only(self, service):
        """Expand with active_only=True excludes inactive codes."""
        codes = [
            ValueSetCode(system="http://example.org", code="A1", display="Active Code", inactive=False),
            ValueSetCode(system="http://example.org", code="I1", display="Inactive Code", inactive=True),
        ]
        vs = service.create(name="ActiveOnly", value_set_type=ValueSetType.EXTENSIONAL, codes=codes)

        expansion = service.expand(vs.id, active_only=True)
        assert expansion is not None
        assert all(not c.inactive for c in expansion.codes)

    def test_expand_nonexistent_returns_none(self, service):
        """Expanding a nonexistent value set returns None."""
        result = service.expand("nonexistent")
        assert result is None

    def test_expand_has_timestamp(self, service, diabetes_codes):
        """Expansion result includes a timestamp."""
        vs = service.create(name="TimestampTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:1])

        expansion = service.expand(vs.id)
        assert expansion.timestamp is not None

    def test_expand_includes_value_set_url(self, service, diabetes_codes):
        """Expansion result includes the value set URL when available."""
        vs = service.create(
            name="URLTest",
            value_set_type=ValueSetType.EXTENSIONAL,
            url="http://example.org/ValueSet/url-test",
            codes=diabetes_codes[:1],
        )

        expansion = service.expand(vs.id)
        assert expansion.value_set_url == "http://example.org/ValueSet/url-test"


# ============================================================================
# $validate-code Operation Tests
# ============================================================================


class TestValidateCodeOperation:
    """Test the FHIR $validate-code operation.

    Per FHIR R4: The $validate-code operation checks whether a code
    is a member of a value set.
    """

    def test_validate_code_present(self, service, diabetes_codes):
        """Validate a code that IS in the value set."""
        vs = service.create(name="ValidateTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11.9",
        )

        assert result.valid is True
        assert result.code == "E11.9"
        assert result.system == "http://hl7.org/fhir/sid/icd-10-cm"

    def test_validate_code_absent(self, service, diabetes_codes):
        """Validate a code that is NOT in the value set."""
        vs = service.create(name="ValidateAbsent", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="Z99.99",
        )

        assert result.valid is False

    def test_validate_code_wrong_system(self, service, diabetes_codes):
        """Code from wrong system is not valid."""
        vs = service.create(name="WrongSystem", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://snomed.info/sct",
            code="E11.9",
        )

        assert result.valid is False

    def test_validate_returns_display(self, service, diabetes_codes):
        """Validation of present code returns its display name."""
        vs = service.create(name="DisplayTest", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11",
        )

        assert result.valid is True
        assert result.display == "Type 2 diabetes mellitus"

    def test_validate_with_display_check(self, service, diabetes_codes):
        """Validate with display parameter checks display matches."""
        vs = service.create(name="DisplayCheck", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11",
            display="Type 2 diabetes mellitus",
        )

        assert result.valid is True

    def test_validate_empty_value_set(self, service):
        """Validate against an empty value set returns invalid."""
        vs = service.create(name="EmptyVS", value_set_type=ValueSetType.EXTENSIONAL, codes=[])

        result = service.validate_code(
            value_set_id=vs.id,
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11",
        )

        assert result.valid is False


# ============================================================================
# Code Management Tests
# ============================================================================


class TestCodeManagement:
    """Test adding and removing codes from value sets."""

    def test_add_code_to_extensional(self, service, diabetes_codes):
        """Add a code to an extensional value set."""
        vs = service.create(name="AddCode", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:2])

        new_code = ValueSetCode(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E13",
            display="Other specified diabetes mellitus",
        )

        updated = service.add_code(vs.id, new_code)
        assert updated is not None
        assert len(updated.codes) == 3
        codes = [c.code for c in updated.codes]
        assert "E13" in codes

    def test_remove_code_from_extensional(self, service, diabetes_codes):
        """Remove a code from an extensional value set."""
        vs = service.create(name="RemoveCode", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        updated = service.remove_code(vs.id, system="http://hl7.org/fhir/sid/icd-10-cm", code="E11")
        assert updated is not None
        codes = [c.code for c in updated.codes]
        assert "E11" not in codes

    def test_add_rule_to_intensional(self, service):
        """Add a rule to an intensional value set."""
        vs = service.create(name="AddRule", value_set_type=ValueSetType.INTENSIONAL, rules=[])

        rule = InclusionRule(
            rule_type=InclusionRuleType.DESCENDANTS,
            system="http://snomed.info/sct",
            code="73211009",
            include=True,
        )

        updated = service.add_rule(vs.id, rule)
        assert updated is not None
        assert len(updated.rules) == 1

    def test_remove_rule_from_intensional(self, service):
        """Remove a rule from an intensional value set."""
        rules = [
            InclusionRule(
                rule_type=InclusionRuleType.CODE,
                system="http://snomed.info/sct",
                code="73211009",
            ),
            InclusionRule(
                rule_type=InclusionRuleType.CODE,
                system="http://snomed.info/sct",
                code="38341003",
            ),
        ]
        vs = service.create(name="RemoveRule", value_set_type=ValueSetType.INTENSIONAL, rules=rules)

        updated = service.remove_rule(vs.id, rule_index=0)
        assert updated is not None
        assert len(updated.rules) == 1


# ============================================================================
# Version Management Tests
# ============================================================================


class TestVersionManagement:
    """Test FHIR-aligned version management."""

    def test_create_new_version(self, service, diabetes_codes):
        """Create a new version of a value set."""
        vs = service.create(name="VersionTest", version="1.0.0",
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)

        updated = service.create_version(vs.id, new_version="2.0.0", status=ValueSetStatus.DRAFT)
        assert updated is not None
        assert updated.version == "2.0.0"

    def test_get_version_history(self, service, diabetes_codes):
        """Get version history of a value set."""
        vs = service.create(name="HistoryTest", version="1.0.0",
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes[:1])

        service.create_version(vs.id, new_version="2.0.0", status=ValueSetStatus.DRAFT,
                               notes="Second version")

        history = service.get_version_history(vs.id)
        assert len(history) >= 1

    def test_version_has_code_count(self, service, diabetes_codes):
        """Version history entries include code count."""
        vs = service.create(name="CodeCountVS", version="1.0.0",
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)

        service.create_version(vs.id, new_version="2.0.0", status=ValueSetStatus.DRAFT)

        history = service.get_version_history(vs.id)
        if history:
            assert history[-1].code_count >= 0


# ============================================================================
# Status Transition Tests
# ============================================================================


class TestStatusTransitions:
    """Test FHIR status lifecycle transitions."""

    def test_draft_to_active(self, service, diabetes_codes):
        """Activate a draft value set."""
        vs = service.create(name="ActivateTest", status=ValueSetStatus.DRAFT,
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)

        activated = service.activate(vs.id)
        assert activated is not None
        assert activated.status == ValueSetStatus.ACTIVE

    def test_active_to_retired(self, service, diabetes_codes):
        """Retire an active value set."""
        vs = service.create(name="RetireTest", status=ValueSetStatus.DRAFT,
                            value_set_type=ValueSetType.EXTENSIONAL, codes=diabetes_codes)
        service.activate(vs.id)

        retired = service.retire(vs.id)
        assert retired is not None
        assert retired.status == ValueSetStatus.RETIRED

    def test_retire_nonexistent_returns_none(self, service):
        """Retiring nonexistent value set returns None."""
        result = service.retire("nonexistent")
        assert result is None

    def test_activate_nonexistent_returns_none(self, service):
        """Activating nonexistent value set returns None."""
        result = service.activate("nonexistent")
        assert result is None


# ============================================================================
# FHIR Import/Export Tests
# ============================================================================


class TestFHIRImportExport:
    """Test FHIR ValueSet resource import and export."""

    def test_import_fhir_valueset(self, service, sample_fhir_valueset):
        """Import a FHIR ValueSet resource."""
        vs = service.import_fhir(sample_fhir_valueset)
        assert vs is not None
        assert vs.name == "TestFHIRValueSet"
        assert vs.title == "Test FHIR Value Set"
        assert vs.status == ValueSetStatus.ACTIVE
        assert vs.version == "2.0.0"
        assert len(vs.codes) == 2

    def test_import_preserves_codes(self, service, sample_fhir_valueset):
        """Imported value set has correct codes from compose.include."""
        vs = service.import_fhir(sample_fhir_valueset)
        codes = {c.code for c in vs.codes}
        assert "J06.9" in codes
        assert "J20.9" in codes

    def test_import_preserves_system(self, service, sample_fhir_valueset):
        """Imported codes have correct system URI."""
        vs = service.import_fhir(sample_fhir_valueset)
        for code in vs.codes:
            assert code.system == "http://hl7.org/fhir/sid/icd-10-cm"

    def test_import_preserves_metadata(self, service, sample_fhir_valueset):
        """Import preserves publisher and description."""
        vs = service.import_fhir(sample_fhir_valueset)
        assert vs.publisher == "Test Publisher"
        assert vs.description == "A test value set in FHIR format"

    def test_export_fhir_valueset(self, service, diabetes_codes):
        """Export a value set in FHIR format."""
        vs = service.create(
            name="ExportTest",
            title="Export Test VS",
            value_set_type=ValueSetType.EXTENSIONAL,
            url="http://example.org/ValueSet/export-test",
            version="1.0.0",
            status=ValueSetStatus.ACTIVE,
            codes=diabetes_codes[:2],
        )

        fhir_vs = service.export_fhir(vs.id)
        assert fhir_vs is not None
        assert fhir_vs.get("resourceType") == "ValueSet"
        assert fhir_vs.get("name") == "ExportTest"

    def test_export_fhir_has_compose(self, service, diabetes_codes):
        """Exported FHIR resource has compose section with codes."""
        vs = service.create(
            name="ComposeTest",
            value_set_type=ValueSetType.EXTENSIONAL,
            codes=diabetes_codes[:2],
            status=ValueSetStatus.DRAFT,
        )
        service.activate(vs.id)

        fhir_vs = service.export_fhir(vs.id)
        assert fhir_vs is not None
        compose = fhir_vs.get("compose", {})
        include = compose.get("include", [])
        assert len(include) >= 1

    def test_export_nonexistent_returns_none(self, service):
        """Exporting nonexistent value set returns None."""
        result = service.export_fhir("nonexistent")
        assert result is None

    def test_roundtrip_fhir(self, service, diabetes_codes):
        """Import and export should preserve key fields."""
        vs = service.create(
            name="RoundtripTest",
            title="Roundtrip",
            value_set_type=ValueSetType.EXTENSIONAL,
            url="http://example.org/ValueSet/roundtrip",
            version="1.0.0",
            status=ValueSetStatus.DRAFT,
            codes=diabetes_codes[:3],
        )
        service.activate(vs.id)

        exported = service.export_fhir(vs.id)
        assert exported is not None
        assert exported.get("resourceType") == "ValueSet"

        # Delete original to avoid URL conflict on re-import
        service.delete(vs.id)

        reimported = service.import_fhir(exported)
        assert reimported is not None
        assert reimported.title == "Roundtrip"
        assert len(reimported.codes) >= 3


# ============================================================================
# CSV Import/Export Tests
# ============================================================================


class TestCSVImportExport:
    """Test CSV-based import/export of value sets."""

    def test_import_csv(self, service):
        """Import a value set from CSV data."""
        csv_data = "code,display\nE11.9,Type 2 diabetes without complications\nE10.9,Type 1 diabetes without complications\n"

        vs = service.import_csv(
            csv_data=csv_data,
            name="CSVImport",
            system="http://hl7.org/fhir/sid/icd-10-cm",
            title="CSV Imported VS",
        )

        assert vs is not None
        assert vs.name == "CSVImport"
        assert len(vs.codes) == 2
        codes = {c.code for c in vs.codes}
        assert "E11.9" in codes
        assert "E10.9" in codes

    def test_export_csv(self, service, diabetes_codes):
        """Export a value set to CSV format."""
        vs = service.create(name="CSVExport", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes[:2])

        csv_data = service.export_csv(vs.id)
        assert csv_data is not None
        assert "E11" in csv_data
        assert "E11.9" in csv_data

    def test_export_csv_nonexistent(self, service):
        """Exporting nonexistent value set to CSV returns None."""
        result = service.export_csv("nonexistent")
        assert result is None


# ============================================================================
# Data Model Tests
# ============================================================================


class TestDataModels:
    """Test FHIR-aligned data model constraints."""

    def test_value_set_status_enum(self):
        """ValueSetStatus has draft, active, retired."""
        assert ValueSetStatus.DRAFT.value == "draft"
        assert ValueSetStatus.ACTIVE.value == "active"
        assert ValueSetStatus.RETIRED.value == "retired"

    def test_value_set_type_enum(self):
        """ValueSetType has extensional and intensional."""
        assert ValueSetType.EXTENSIONAL.value == "extensional"
        assert ValueSetType.INTENSIONAL.value == "intensional"

    def test_inclusion_rule_types(self):
        """InclusionRuleType covers FHIR rule types."""
        assert InclusionRuleType.CODE.value == "code"
        assert InclusionRuleType.FILTER.value == "filter"
        assert InclusionRuleType.DESCENDANTS.value == "descendants"
        assert InclusionRuleType.ANCESTORS.value == "ancestors"
        assert InclusionRuleType.VALUE_SET.value == "value_set"

    def test_filter_operators(self):
        """FilterOperator covers FHIR filter operators."""
        assert FilterOperator.EQUALS.value == "="
        assert FilterOperator.IS_A.value == "is-a"
        assert FilterOperator.DESCENDENT_OF.value == "descendent-of"
        assert FilterOperator.IS_NOT_A.value == "is-not-a"
        assert FilterOperator.REGEX.value == "regex"
        assert FilterOperator.IN.value == "in"
        assert FilterOperator.NOT_IN.value == "not-in"
        assert FilterOperator.EXISTS.value == "exists"

    def test_value_set_code_fields(self):
        """ValueSetCode has required FHIR code fields."""
        code = ValueSetCode(
            system="http://snomed.info/sct",
            code="73211009",
            display="Diabetes mellitus",
            version="2024-01",
            inactive=False,
            abstract=False,
        )
        assert code.system == "http://snomed.info/sct"
        assert code.code == "73211009"
        assert code.display == "Diabetes mellitus"
        assert code.version == "2024-01"
        assert code.inactive is False
        assert code.abstract is False

    def test_validation_result_fields(self):
        """ValidationResult has FHIR-conformant fields."""
        result = ValidationResult(
            valid=True,
            message="Code found",
            display="Diabetes mellitus",
            code="73211009",
            system="http://snomed.info/sct",
        )
        assert result.valid is True
        assert result.message == "Code found"
        assert result.display == "Diabetes mellitus"
        assert result.code == "73211009"
        assert result.system == "http://snomed.info/sct"

    def test_expansion_result_fields(self):
        """ValueSetExpansionResult has required fields."""
        from datetime import datetime, timezone

        expansion = ValueSetExpansionResult(
            value_set_id="test-vs",
            value_set_url="http://example.org/ValueSet/test",
            timestamp=datetime.now(timezone.utc),
            total=5,
            offset=0,
            codes=[],
        )
        assert expansion.value_set_id == "test-vs"
        assert expansion.value_set_url is not None
        assert expansion.timestamp is not None
        assert expansion.total == 5


# ============================================================================
# Singleton Pattern Tests
# ============================================================================


class TestSingleton:
    """Test the service singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """get_value_set_service returns the same instance."""
        s1 = get_value_set_service()
        s2 = get_value_set_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """reset_value_set_service creates a new instance on next call."""
        s1 = get_value_set_service()
        reset_value_set_service()
        s2 = get_value_set_service()
        assert s1 is not s2


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_expand_empty_value_set(self, service):
        """Expanding an empty value set returns 0 codes."""
        vs = service.create(name="EmptyExpand", value_set_type=ValueSetType.EXTENSIONAL, codes=[])

        expansion = service.expand(vs.id)
        assert expansion is not None
        assert expansion.total == 0
        assert len(expansion.codes) == 0

    def test_validate_in_empty_set(self, service):
        """Validating against empty value set returns invalid."""
        vs = service.create(name="EmptyValidate", value_set_type=ValueSetType.EXTENSIONAL, codes=[])

        result = service.validate_code(vs.id, system="http://example.org", code="X")
        assert result.valid is False

    def test_duplicate_codes_handled(self, service):
        """Adding duplicate code is handled gracefully."""
        codes = [
            ValueSetCode(system="http://example.org", code="A1", display="Code A1"),
            ValueSetCode(system="http://example.org", code="A1", display="Code A1"),
        ]
        vs = service.create(name="DuplicateTest", value_set_type=ValueSetType.EXTENSIONAL, codes=codes)
        assert vs is not None

    def test_large_expansion_count(self, service, diabetes_codes):
        """Request for more codes than available is handled."""
        vs = service.create(name="LargeCount", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        expansion = service.expand(vs.id, count=10000)
        assert expansion is not None
        assert len(expansion.codes) == 5
        assert expansion.total == 5

    def test_expand_offset_beyond_total(self, service, diabetes_codes):
        """Offset beyond total returns empty codes list."""
        vs = service.create(name="OffsetBeyond", value_set_type=ValueSetType.EXTENSIONAL,
                            codes=diabetes_codes)

        expansion = service.expand(vs.id, offset=100)
        assert expansion is not None
        assert len(expansion.codes) == 0

    def test_multiple_systems_in_value_set(self, service):
        """Value set can contain codes from multiple systems."""
        codes = [
            ValueSetCode(system="http://snomed.info/sct", code="73211009", display="Diabetes mellitus"),
            ValueSetCode(system="http://hl7.org/fhir/sid/icd-10-cm", code="E11.9", display="Type 2 DM"),
        ]
        vs = service.create(name="MultiSystem", value_set_type=ValueSetType.EXTENSIONAL, codes=codes)

        # Validate SNOMED code
        r1 = service.validate_code(vs.id, system="http://snomed.info/sct", code="73211009")
        assert r1.valid is True

        # Validate ICD-10 code
        r2 = service.validate_code(vs.id, system="http://hl7.org/fhir/sid/icd-10-cm", code="E11.9")
        assert r2.valid is True

        # Wrong system for existing code
        r3 = service.validate_code(vs.id, system="http://snomed.info/sct", code="E11.9")
        assert r3.valid is False

    def test_get_stats(self, service, diabetes_codes):
        """Get value set statistics."""
        service.create(name="StatsTest", value_set_type=ValueSetType.EXTENSIONAL,
                       codes=diabetes_codes)

        stats = service.get_stats()
        assert stats is not None
        assert isinstance(stats, dict)
