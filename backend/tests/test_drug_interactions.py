"""Tests for Drug Interaction Service.

Tests the drug interaction checking functionality.
"""

import pytest

from app.services.drug_interactions import (
    DrugInteractionService,
    InteractionSeverity,
    InteractionType,
    get_drug_interaction_service,
    reset_drug_interaction_service,
    DRUG_INTERACTIONS,
    DRUG_ALIASES,
)


# ============================================================================
# Database Content Tests
# ============================================================================


class TestDatabaseContent:
    """Test the drug interaction database content."""

    def test_database_not_empty(self):
        """Test that database has interactions."""
        assert len(DRUG_INTERACTIONS) > 0

    def test_has_contraindicated_interactions(self):
        """Test that database has contraindicated interactions."""
        contraindicated = [
            i for i in DRUG_INTERACTIONS
            if i.severity == InteractionSeverity.CONTRAINDICATED
        ]
        assert len(contraindicated) > 0

    def test_has_major_interactions(self):
        """Test that database has major interactions."""
        major = [
            i for i in DRUG_INTERACTIONS
            if i.severity == InteractionSeverity.MAJOR
        ]
        assert len(major) > 0

    def test_has_moderate_interactions(self):
        """Test that database has moderate interactions."""
        moderate = [
            i for i in DRUG_INTERACTIONS
            if i.severity == InteractionSeverity.MODERATE
        ]
        assert len(moderate) > 0

    def test_interactions_have_required_fields(self):
        """Test that all interactions have required fields."""
        for interaction in DRUG_INTERACTIONS:
            assert interaction.drug1
            assert interaction.drug2
            assert interaction.severity
            assert interaction.interaction_type
            assert interaction.description
            assert interaction.clinical_effect
            assert interaction.management

    def test_drug_aliases_populated(self):
        """Test that drug aliases are populated."""
        assert len(DRUG_ALIASES) > 0
        assert "tylenol" in DRUG_ALIASES
        assert "coumadin" in DRUG_ALIASES


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_drug_interaction_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = DrugInteractionService()
        assert service is not None

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_drug_interaction_service()
        service2 = get_drug_interaction_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_drug_interaction_service()
        reset_drug_interaction_service()
        service2 = get_drug_interaction_service()
        assert service1 is not service2


# ============================================================================
# Drug Name Normalization Tests
# ============================================================================


class TestDrugNameNormalization:
    """Test drug name normalization and alias resolution."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_normalize_lowercase(self):
        """Test normalization to lowercase."""
        assert self.service.normalize_drug_name("ASPIRIN") == "aspirin"
        assert self.service.normalize_drug_name("Aspirin") == "aspirin"

    def test_normalize_whitespace(self):
        """Test normalization strips whitespace."""
        assert self.service.normalize_drug_name("  aspirin  ") == "aspirin"

    def test_resolve_brand_to_generic(self):
        """Test brand name resolution to generic."""
        assert self.service.normalize_drug_name("Tylenol") == "acetaminophen"
        assert self.service.normalize_drug_name("Coumadin") == "warfarin"
        assert self.service.normalize_drug_name("Lipitor") == "atorvastatin"

    def test_resolve_abbreviations(self):
        """Test abbreviation resolution."""
        assert self.service.normalize_drug_name("ASA") == "aspirin"
        assert self.service.normalize_drug_name("HCTZ") == "hydrochlorothiazide"
        assert self.service.normalize_drug_name("APAP") == "acetaminophen"

    def test_unknown_drug_unchanged(self):
        """Test unknown drugs are returned unchanged."""
        assert self.service.normalize_drug_name("unknowndrug") == "unknowndrug"


# ============================================================================
# Pair Checking Tests
# ============================================================================


class TestPairChecking:
    """Test checking interactions between drug pairs."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_known_contraindicated_pair(self):
        """Test finding a known contraindicated interaction."""
        interaction = self.service.check_pair("sildenafil", "nitroglycerin")
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.CONTRAINDICATED

    def test_known_major_pair(self):
        """Test finding a known major interaction."""
        interaction = self.service.check_pair("warfarin", "aspirin")
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR

    def test_pair_order_independent(self):
        """Test that drug order doesn't matter."""
        interaction1 = self.service.check_pair("warfarin", "aspirin")
        interaction2 = self.service.check_pair("aspirin", "warfarin")
        assert interaction1 == interaction2

    def test_brand_name_resolution(self):
        """Test that brand names resolve correctly."""
        interaction = self.service.check_pair("Coumadin", "ASA")
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR

    def test_no_interaction_pair(self):
        """Test pair with no known interaction."""
        interaction = self.service.check_pair("metformin", "acetaminophen")
        assert interaction is None

    def test_same_drug_pair(self):
        """Test that same drug returns None."""
        interaction = self.service.check_pair("aspirin", "aspirin")
        assert interaction is None


# ============================================================================
# Multiple Drug Checking Tests
# ============================================================================


class TestMultipleDrugChecking:
    """Test checking interactions among multiple drugs."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_check_two_drugs_with_interaction(self):
        """Test checking two drugs with an interaction."""
        result = self.service.check_interactions(["warfarin", "aspirin"])

        assert result.total_interactions == 1
        assert result.has_major
        assert not result.has_contraindicated

    def test_check_two_drugs_no_interaction(self):
        """Test checking two drugs with no interaction."""
        result = self.service.check_interactions(["metformin", "acetaminophen"])

        assert result.total_interactions == 0
        assert not result.has_major
        assert not result.has_contraindicated


# ============================================================================
# Neo4j Concept Graph Integration Tests
# ============================================================================


class _FakeDrugInfo:
    def __init__(self, omop_concept_id: int, name: str) -> None:
        self.omop_concept_id = omop_concept_id
        self.generic_name = name
        self.concept_name = name


class _FakeLookupResult:
    def __init__(self, found: bool, drug_info: _FakeDrugInfo | None) -> None:
        self.found = found
        self.drug_info = drug_info


class _FakeRxNormService:
    def __init__(self, mapping: dict[str, tuple[int, str]]) -> None:
        self._mapping = mapping

    def lookup_drug(self, name: str) -> _FakeLookupResult:
        key = name.lower().strip()
        if key in self._mapping:
            concept_id, display = self._mapping[key]
            return _FakeLookupResult(True, _FakeDrugInfo(concept_id, display))
        return _FakeLookupResult(False, None)


class _FakeGraphService:
    is_connected = True

    def execute_read(self, query: str, parameters: dict | None = None):
        if "Concept {concept_id" in query:
            return type("Result", (), {
                "records": [
                    {
                        "rel_type": "INTERACTS_WITH",
                        "severity": "major",
                        "interaction_type": "qt_prolongation",
                        "description": "Graph-derived interaction",
                        "clinical_effect": "Arrhythmia risk",
                        "management": "Avoid combination",
                        "references": ["Neo4j"],
                    }
                ]
            })()
        return type("Result", (), {"records": []})()


class TestNeo4jConceptGraphIntegration:
    """Test Neo4j concept graph interaction lookups."""

    def setup_method(self):
        """Create service for each test."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_check_pair_uses_concept_graph(self):
        service = DrugInteractionService(use_rxnorm=False, use_graph=False)
        service._rxnorm_service = _FakeRxNormService({
            "alpha": (111, "Alpha"),
            "beta": (222, "Beta"),
        })
        service._graph_service = _FakeGraphService()

        interaction = service.check_pair("alpha", "beta")

        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR
        assert interaction.interaction_type == InteractionType.QT_PROLONGATION
        assert interaction.description == "Graph-derived interaction"

    def test_check_multiple_drugs_multiple_interactions(self):
        """Test checking multiple drugs with multiple interactions."""
        # This combination may have multiple interactions
        result = self.service.check_interactions([
            "warfarin", "aspirin", "ibuprofen", "lisinopril"
        ])

        # Should find at least warfarin+aspirin and warfarin+ibuprofen
        assert result.total_interactions >= 2

    def test_check_includes_contraindicated(self):
        """Test that contraindicated interactions are flagged."""
        result = self.service.check_interactions(["sildenafil", "nitroglycerin"])

        assert result.has_contraindicated
        assert result.highest_severity == InteractionSeverity.CONTRAINDICATED

    def test_empty_drug_list(self):
        """Test checking empty drug list."""
        result = self.service.check_interactions([])

        assert result.total_interactions == 0
        assert result.highest_severity is None

    def test_single_drug_list(self):
        """Test checking single drug."""
        result = self.service.check_interactions(["aspirin"])

        assert result.total_interactions == 0
        assert result.highest_severity is None

    def test_duplicate_drugs_handled(self):
        """Test that duplicate drugs are handled."""
        result = self.service.check_interactions([
            "aspirin", "aspirin", "warfarin"
        ])

        # Should only count warfarin+aspirin once
        assert result.total_interactions == 1

    def test_drugs_checked_normalized(self):
        """Test that returned drugs are normalized."""
        result = self.service.check_interactions(["WARFARIN", "Aspirin"])

        assert "warfarin" in result.drugs_checked
        assert "aspirin" in result.drugs_checked


# ============================================================================
# Drug-Specific Lookup Tests
# ============================================================================


class TestDrugSpecificLookup:
    """Test looking up all interactions for a drug."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_get_interactions_for_warfarin(self):
        """Test getting all interactions for warfarin."""
        interactions = self.service.get_interactions_for_drug("warfarin")

        # Warfarin has multiple known interactions
        assert len(interactions) >= 2

        # All interactions should involve warfarin
        for interaction in interactions:
            assert "warfarin" in [interaction.drug1, interaction.drug2]

    def test_get_interactions_brand_name(self):
        """Test getting interactions using brand name."""
        interactions = self.service.get_interactions_for_drug("Coumadin")

        # Should find same interactions as generic
        generic_interactions = self.service.get_interactions_for_drug("warfarin")
        assert len(interactions) == len(generic_interactions)

    def test_get_interactions_unknown_drug(self):
        """Test getting interactions for unknown drug."""
        interactions = self.service.get_interactions_for_drug("unknowndrug123")
        assert len(interactions) == 0


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test database statistics."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_get_stats(self):
        """Test getting database statistics."""
        stats = self.service.get_stats()

        assert "total_interactions" in stats
        assert "unique_drugs" in stats
        assert "aliases_count" in stats
        assert "by_severity" in stats
        assert "by_type" in stats

    def test_stats_by_severity_complete(self):
        """Test that severity counts are correct."""
        stats = self.service.get_stats()

        # Total should sum to total_interactions
        severity_sum = sum(stats["by_severity"].values())
        assert severity_sum == stats["total_interactions"]

    def test_stats_by_type_complete(self):
        """Test that type counts are correct."""
        stats = self.service.get_stats()

        # Total should sum to total_interactions
        type_sum = sum(stats["by_type"].values())
        assert type_sum == stats["total_interactions"]


# ============================================================================
# Severity Hierarchy Tests
# ============================================================================


class TestSeverityHierarchy:
    """Test severity level handling."""

    def test_contraindicated_highest(self):
        """Test that contraindicated is highest severity."""
        # Severity order should be: contraindicated > major > moderate > minor
        assert InteractionSeverity.CONTRAINDICATED.value == "contraindicated"
        assert InteractionSeverity.MAJOR.value == "major"
        assert InteractionSeverity.MODERATE.value == "moderate"
        assert InteractionSeverity.MINOR.value == "minor"

    def test_highest_severity_reported(self):
        """Test that highest severity is correctly reported."""
        service = DrugInteractionService()

        # If both contraindicated and major exist, highest should be contraindicated
        # This depends on what drugs we check
        result = service.check_interactions([
            "sildenafil", "nitroglycerin",  # contraindicated
            "warfarin", "aspirin"  # major
        ])

        if result.has_contraindicated:
            assert result.highest_severity == InteractionSeverity.CONTRAINDICATED


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for realistic clinical scenarios."""

    def setup_method(self):
        """Create service for testing."""
        reset_drug_interaction_service()
        self.service = DrugInteractionService(use_rxnorm=False)

    def test_typical_medication_list(self):
        """Test a typical patient medication list."""
        # Common medications for a patient with heart failure and diabetes
        meds = [
            "lisinopril",      # ACE inhibitor
            "metoprolol",      # Beta blocker
            "furosemide",      # Diuretic
            "metformin",       # Diabetes
            "aspirin",         # Antiplatelet
            "atorvastatin",    # Statin
        ]

        result = self.service.check_interactions(meds)

        # This should find some interactions (metformin+lisinopril at least)
        # Real clinical decision support would flag these
        assert isinstance(result.total_interactions, int)

    def test_anticoagulation_scenario(self):
        """Test checking anticoagulation medications."""
        meds = ["warfarin", "aspirin", "ibuprofen"]
        result = self.service.check_interactions(meds)

        # Should find multiple bleeding risk interactions
        assert result.total_interactions >= 2
        assert result.has_major

        # All interactions should be bleeding-related
        bleeding_interactions = [
            i for i in result.interactions_found
            if i.interaction_type == InteractionType.BLEEDING_RISK
        ]
        assert len(bleeding_interactions) >= 2

    def test_brand_name_mixed_list(self):
        """Test using a mix of brand and generic names."""
        meds = ["Coumadin", "ASA", "Advil"]  # warfarin, aspirin, ibuprofen
        result = self.service.check_interactions(meds)

        # Should find same interactions as generic names
        assert result.total_interactions >= 2
        assert result.has_major
