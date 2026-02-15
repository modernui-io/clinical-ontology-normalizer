"""Tests for Differential Diagnosis Service.

Tests the differential diagnosis generation functionality.
"""

import pytest

from app.services.differential_diagnosis import (
    ClinicalDomain,
    DiagnosisUrgency,
    DifferentialDiagnosisService,
    DifferentialResult,
    get_differential_diagnosis_service,
    reset_differential_diagnosis_service,
    DIAGNOSIS_TEMPLATES,
    FINDING_ALIASES,
)


# ============================================================================
# Service Tests
# ============================================================================


class TestServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_differential_diagnosis_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = DifferentialDiagnosisService()
        assert service is not None

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_differential_diagnosis_service()
        service2 = get_differential_diagnosis_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_differential_diagnosis_service()
        reset_differential_diagnosis_service()
        service2 = get_differential_diagnosis_service()
        assert service1 is not service2


# ============================================================================
# Database Content Tests
# ============================================================================


class TestDatabaseContent:
    """Test the diagnosis database content."""

    def test_database_not_empty(self):
        """Test that database has diagnoses."""
        assert len(DIAGNOSIS_TEMPLATES) > 0

    def test_diagnosis_has_required_fields(self):
        """Test that all diagnoses have required fields."""
        for dx in DIAGNOSIS_TEMPLATES:
            assert dx.name
            assert dx.domain
            assert dx.urgency
            assert len(dx.classic_findings) > 0 or len(dx.common_findings) > 0
            assert len(dx.key_features) > 0
            assert len(dx.recommended_workup) > 0

    def test_has_emergent_diagnoses(self):
        """Test that database has emergent diagnoses."""
        emergent = [dx for dx in DIAGNOSIS_TEMPLATES if dx.urgency == DiagnosisUrgency.EMERGENT]
        assert len(emergent) > 0

    def test_has_multiple_domains(self):
        """Test that database covers multiple clinical domains."""
        domains = set(dx.domain for dx in DIAGNOSIS_TEMPLATES)
        assert len(domains) >= 5

    def test_aliases_exist(self):
        """Test that finding aliases are defined."""
        assert len(FINDING_ALIASES) > 0
        assert "chest pain" in FINDING_ALIASES
        assert "shortness of breath" in FINDING_ALIASES


# ============================================================================
# Finding Normalization Tests
# ============================================================================


class TestFindingNormalization:
    """Test finding normalization."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_normalize_chest_pain(self):
        """Test normalizing chest pain variants."""
        assert self.service.normalize_finding("chest pain") == "chest_pain"
        assert self.service.normalize_finding("Chest Pain") == "chest_pain"
        assert self.service.normalize_finding("angina") == "chest_pain"

    def test_normalize_dyspnea(self):
        """Test normalizing shortness of breath variants."""
        assert self.service.normalize_finding("shortness of breath") == "dyspnea"
        assert self.service.normalize_finding("SOB") == "dyspnea"
        assert self.service.normalize_finding("difficulty breathing") == "dyspnea"

    def test_normalize_unknown_finding(self):
        """Test normalizing unknown finding."""
        result = self.service.normalize_finding("some unknown symptom")
        assert result == "some_unknown_symptom"


# ============================================================================
# Differential Generation Tests
# ============================================================================


class TestDifferentialGeneration:
    """Test differential diagnosis generation."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_generate_basic_differential(self):
        """Test generating a basic differential."""
        result = self.service.generate_differential(
            findings=["chest pain", "shortness of breath"]
        )

        assert isinstance(result, DifferentialResult)
        assert len(result.differential) > 0
        assert len(result.presenting_findings) == 2

    def test_chest_pain_differential_includes_acs(self):
        """Test that chest pain differential includes ACS."""
        result = self.service.generate_differential(
            findings=["chest pain", "diaphoresis", "radiating to arm"]
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Acute Coronary Syndrome (ACS)" in diagnoses

    def test_classic_acs_presentation_ranks_high(self):
        """Test that classic ACS presentation ranks ACS highly."""
        result = self.service.generate_differential(
            findings=["chest pain", "diaphoresis", "crushing pain", "radiating to arm", "nausea"]
        )

        # ACS should be in top 3 for this classic presentation
        top_3_names = [dx.name for dx in result.differential[:3]]
        assert "Acute Coronary Syndrome (ACS)" in top_3_names

    def test_respiratory_symptoms_include_pneumonia(self):
        """Test respiratory symptoms include pneumonia."""
        result = self.service.generate_differential(
            findings=["fever", "productive cough", "shortness of breath"]
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Community-Acquired Pneumonia" in diagnoses

    def test_abdominal_pain_differential(self):
        """Test abdominal pain differential."""
        result = self.service.generate_differential(
            findings=["right lower quadrant pain", "fever", "nausea"]
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Acute Appendicitis" in diagnoses

    def test_neurological_differential(self):
        """Test neurological differential."""
        result = self.service.generate_differential(
            findings=["arm weakness", "facial droop", "slurred speech"]
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Ischemic Stroke" in diagnoses

    def test_empty_findings_returns_empty(self):
        """Test that empty findings returns empty differential."""
        result = self.service.generate_differential(findings=[])
        assert len(result.differential) == 0

    def test_unknown_findings_returns_empty(self):
        """Test that completely unknown findings returns empty."""
        result = self.service.generate_differential(
            findings=["xyzzyx symptom", "abc123 sign"]
        )
        assert len(result.differential) == 0


# ============================================================================
# Demographic Adjustment Tests
# ============================================================================


class TestDemographicAdjustment:
    """Test demographic adjustments."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_age_adjustment_cardiac(self):
        """Test age adjustment for cardiac conditions."""
        young = self.service.generate_differential(
            findings=["chest pain", "palpitations"],
            age=25,
        )
        old = self.service.generate_differential(
            findings=["chest pain", "palpitations"],
            age=65,
        )

        # Get ACS score for each
        young_acs = next((dx for dx in young.differential if "ACS" in dx.name), None)
        old_acs = next((dx for dx in old.differential if "ACS" in dx.name), None)

        # Older patient should have higher ranking score
        if young_acs and old_acs:
            assert old_acs.ranking_score >= young_acs.ranking_score

    def test_gender_adjustment_uti(self):
        """Test gender adjustment for UTI."""
        male = self.service.generate_differential(
            findings=["dysuria", "urinary frequency"],
            gender="male",
        )
        female = self.service.generate_differential(
            findings=["dysuria", "urinary frequency"],
            gender="female",
        )

        male_uti = next((dx for dx in male.differential if "UTI" in dx.name), None)
        female_uti = next((dx for dx in female.differential if "UTI" in dx.name), None)

        # UTI more common in females
        if male_uti and female_uti:
            assert female_uti.ranking_score >= male_uti.ranking_score

    def test_gender_adjustment_gout(self):
        """Test gender adjustment for gout."""
        male = self.service.generate_differential(
            findings=["joint pain", "joint swelling"],
            gender="male",
        )
        female = self.service.generate_differential(
            findings=["joint pain", "joint swelling"],
            gender="female",
        )

        male_gout = next((dx for dx in male.differential if "Gout" in dx.name), None)
        female_gout = next((dx for dx in female.differential if "Gout" in dx.name), None)

        # Gout more common in males
        if male_gout and female_gout:
            assert male_gout.ranking_score >= female_gout.ranking_score


# ============================================================================
# Result Structure Tests
# ============================================================================


class TestResultStructure:
    """Test result structure."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_result_has_required_fields(self):
        """Test that results have all required fields."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea"]
        )

        assert hasattr(result, "presenting_findings")
        assert hasattr(result, "differential")
        assert hasattr(result, "red_flag_diagnoses")
        assert hasattr(result, "cannot_miss_diagnoses")
        assert hasattr(result, "suggested_history")
        assert hasattr(result, "suggested_exam")

    def test_diagnosis_candidate_structure(self):
        """Test that diagnosis candidates have all fields."""
        result = self.service.generate_differential(
            findings=["chest pain", "diaphoresis"]
        )

        if result.differential:
            dx = result.differential[0]
            assert hasattr(dx, "name")
            assert hasattr(dx, "domain")
            assert hasattr(dx, "urgency")
            assert hasattr(dx, "ranking_score")
            assert hasattr(dx, "supporting_findings")
            assert hasattr(dx, "red_flags")
            assert hasattr(dx, "recommended_workup")

    def test_ranking_score_range(self):
        """Test that ranking scores are in valid range."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea", "nausea"]
        )

        for dx in result.differential:
            assert 0.0 <= dx.ranking_score <= 1.0

    def test_red_flag_diagnoses_identified(self):
        """Test that red flag diagnoses are identified."""
        result = self.service.generate_differential(
            findings=["chest pain", "diaphoresis", "crushing pain"]
        )

        # ACS is emergent and should be flagged
        assert len(result.red_flag_diagnoses) > 0

    def test_suggested_history_generated(self):
        """Test that history suggestions are generated."""
        result = self.service.generate_differential(
            findings=["chest pain"]
        )

        assert len(result.suggested_history) > 0

    def test_suggested_exam_generated(self):
        """Test that exam suggestions are generated."""
        result = self.service.generate_differential(
            findings=["chest pain", "dyspnea"]
        )

        assert len(result.suggested_exam) > 0


# ============================================================================
# Lookup Tests
# ============================================================================


class TestLookup:
    """Test diagnosis lookup functions."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_get_diagnoses_by_domain(self):
        """Test getting diagnoses by domain."""
        cardiac = self.service.get_diagnoses_by_domain(ClinicalDomain.CARDIOVASCULAR)
        assert len(cardiac) > 0
        assert all(dx.domain == ClinicalDomain.CARDIOVASCULAR for dx in cardiac)

    def test_get_diagnosis_by_name(self):
        """Test getting diagnosis by name."""
        dx = self.service.get_diagnosis_by_name("Acute Coronary Syndrome (ACS)")
        assert dx is not None
        assert dx.urgency == DiagnosisUrgency.EMERGENT

    def test_get_diagnosis_case_insensitive(self):
        """Test case insensitive lookup."""
        dx = self.service.get_diagnosis_by_name("acute coronary syndrome (acs)")
        assert dx is not None

    def test_get_nonexistent_diagnosis(self):
        """Test getting nonexistent diagnosis."""
        dx = self.service.get_diagnosis_by_name("Not A Real Diagnosis")
        assert dx is None


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test service statistics."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_get_stats(self):
        """Test getting service statistics."""
        stats = self.service.get_stats()

        assert "total_diagnoses" in stats
        assert "total_findings" in stats
        assert "by_domain" in stats
        assert "by_urgency" in stats

    def test_stats_count_correct(self):
        """Test that stats counts are correct."""
        stats = self.service.get_stats()

        assert stats["total_diagnoses"] == len(DIAGNOSIS_TEMPLATES)
        assert sum(stats["by_domain"].values()) == stats["total_diagnoses"]


# ============================================================================
# Clinical Scenario Tests
# ============================================================================


class TestClinicalScenarios:
    """Test realistic clinical scenarios."""

    def setup_method(self):
        """Create service for testing."""
        reset_differential_diagnosis_service()
        self.service = DifferentialDiagnosisService()

    def test_mi_presentation(self):
        """Test classic MI presentation."""
        result = self.service.generate_differential(
            findings=[
                "chest pain",
                "crushing pain",
                "radiating to arm",
                "diaphoresis",
                "nausea",
            ],
            age=62,
            gender="male",
        )

        # ACS should be top diagnosis
        assert result.differential[0].name == "Acute Coronary Syndrome (ACS)"
        assert result.differential[0].urgency == DiagnosisUrgency.EMERGENT

    def test_pe_presentation(self):
        """Test pulmonary embolism presentation."""
        result = self.service.generate_differential(
            findings=[
                "shortness of breath",
                "pleuritic pain",
                "palpitations",
                "leg swelling",
            ],
            age=45,
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Pulmonary Embolism" in diagnoses

    def test_appendicitis_presentation(self):
        """Test appendicitis presentation."""
        result = self.service.generate_differential(
            findings=[
                "right lower quadrant pain",
                "fever",
                "nausea",
                "vomiting",
            ],
            age=22,
        )

        # Appendicitis should rank highly
        top_5_names = [dx.name for dx in result.differential[:5]]
        assert "Acute Appendicitis" in top_5_names

    def test_stroke_presentation(self):
        """Test stroke presentation."""
        result = self.service.generate_differential(
            findings=[
                "arm weakness",
                "facial droop",
                "slurred speech",
                "confusion",
            ],
            age=70,
        )

        # Stroke should be top diagnosis
        top_3_names = [dx.name for dx in result.differential[:3]]
        assert "Ischemic Stroke" in top_3_names
        assert "Ischemic Stroke" in result.cannot_miss_diagnoses

    def test_uti_presentation(self):
        """Test UTI presentation."""
        result = self.service.generate_differential(
            findings=[
                "dysuria",
                "urinary frequency",
                "urinary urgency",
            ],
            age=28,
            gender="female",
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Urinary Tract Infection" in diagnoses

    def test_chf_exacerbation(self):
        """Test CHF exacerbation presentation."""
        result = self.service.generate_differential(
            findings=[
                "shortness of breath",
                "leg swelling",
                "orthopnea",
                "fatigue",
            ],
            age=72,
        )

        diagnoses = [dx.name for dx in result.differential]
        assert "Congestive Heart Failure (CHF)" in diagnoses
