"""Tests for Vocabulary Update Regression Testing.

Dir-CI-3.5: Vocabulary Update Regression Testing - verifies baseline capture,
change detection (concept ID, deprecation, domain, new mapping, confidence),
high-risk identification, trial-impacting change detection, baseline
serialization/deserialization, and the 500+ entry fixture.
"""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from app.schemas.vocab_regression import (
    ChangeType,
    RiskLevel,
    VocabBaseline,
    VocabChange,
    VocabMapping,
    VocabRegressionReport,
    VocabUpdatePreview,
)
from app.services.vocab_regression_service import (
    TRIAL_CRITICAL_TERMS,
    VocabRegressionService,
    get_vocab_regression_service,
    reset_vocab_regression_service,
)

# Path to the 500+ entry fixture
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vocab_regression_baseline.json"


# ============================================================================
# Helpers
# ============================================================================


def _make_mapping(
    term: str,
    concept_id: int = 12345,
    concept_name: str = "Test Concept",
    domain_id: str = "Condition",
    vocabulary_id: str = "SNOMED",
    standard_concept: str = "S",
    confidence: float = 1.0,
) -> VocabMapping:
    """Create a VocabMapping for testing."""
    return VocabMapping(
        term=term,
        concept_id=concept_id,
        concept_name=concept_name,
        domain_id=domain_id,
        vocabulary_id=vocabulary_id,
        standard_concept=standard_concept,
        confidence=confidence,
    )


def _load_fixture_mappings() -> list[VocabMapping]:
    """Load mappings from the fixture file."""
    data = json.loads(FIXTURE_PATH.read_text())
    return [VocabMapping(**m) for m in data["mappings"]]


# ============================================================================
# Schema tests
# ============================================================================


class TestVocabRegressionSchemas:
    """Test Pydantic schema construction and validation."""

    def test_vocab_mapping_creation(self):
        mapping = VocabMapping(
            term="type 2 diabetes",
            concept_id=201826,
            concept_name="Type 2 diabetes mellitus",
            domain_id="Condition",
            vocabulary_id="SNOMED",
            standard_concept="S",
            confidence=0.98,
        )
        assert mapping.term == "type 2 diabetes"
        assert mapping.concept_id == 201826
        assert mapping.domain_id == "Condition"
        assert mapping.confidence == 0.98

    def test_vocab_mapping_defaults(self):
        mapping = VocabMapping(
            term="test",
            concept_id=1,
            concept_name="Test",
            domain_id="Condition",
            vocabulary_id="SNOMED",
        )
        assert mapping.standard_concept is None
        assert mapping.confidence == 1.0
        assert mapping.concept_class_id is None

    def test_vocab_baseline_creation(self):
        mappings = [
            _make_mapping("diabetes", concept_id=201826),
            _make_mapping("asthma", concept_id=317009),
        ]
        baseline = VocabBaseline(
            name="test-baseline",
            version="v5.0",
            mappings=mappings,
        )
        assert baseline.name == "test-baseline"
        assert baseline.version == "v5.0"
        assert baseline.total_count == 2
        assert len(baseline.mappings) == 2

    def test_vocab_baseline_auto_count(self):
        mappings = [_make_mapping(f"term_{i}") for i in range(10)]
        baseline = VocabBaseline(
            name="auto-count",
            version="v1",
            mappings=mappings,
        )
        assert baseline.total_count == 10

    def test_vocab_change_creation(self):
        change = VocabChange(
            term="diabetes",
            change_type=ChangeType.ID_CHANGED,
            old_value="Type 2 DM (201826)",
            new_value="Type 2 DM (999999)",
            old_concept_id=201826,
            new_concept_id=999999,
            domain_id="Condition",
            risk_level=RiskLevel.HIGH,
            detail="Concept ID changed",
        )
        assert change.change_type == ChangeType.ID_CHANGED
        assert change.risk_level == RiskLevel.HIGH
        assert change.old_concept_id == 201826

    def test_vocab_regression_report_creation(self):
        report = VocabRegressionReport(
            baseline_name="test",
            total_checked=100,
            unchanged=90,
            changed=10,
            high_risk_changes=2,
            medium_risk_changes=3,
            low_risk_changes=5,
        )
        assert report.total_checked == 100
        assert report.unchanged == 90
        assert report.changed == 10
        assert report.has_breaking_changes is True
        assert report.change_rate_pct == 10.0

    def test_vocab_regression_report_no_breaking_changes(self):
        report = VocabRegressionReport(
            baseline_name="safe",
            total_checked=50,
            unchanged=48,
            changed=2,
            high_risk_changes=0,
            medium_risk_changes=1,
            low_risk_changes=1,
        )
        assert report.has_breaking_changes is False

    def test_vocab_regression_report_change_rate_zero(self):
        report = VocabRegressionReport(
            baseline_name="empty",
            total_checked=0,
        )
        assert report.change_rate_pct == 0.0


# ============================================================================
# Service - Baseline capture tests
# ============================================================================


class TestBaselineCapture:
    """Test baseline capture and retrieval."""

    @pytest.fixture
    def service(self):
        return VocabRegressionService()

    def test_capture_baseline(self, service):
        mappings = [
            _make_mapping("diabetes", concept_id=201826),
            _make_mapping("asthma", concept_id=317009),
            _make_mapping("hypertension", concept_id=320128),
        ]

        baseline = service.capture_baseline(
            "test-v1",
            mappings,
            version="v5.0",
            description="Test baseline",
            persist=False,
        )

        assert baseline.name == "test-v1"
        assert baseline.version == "v5.0"
        assert baseline.total_count == 3
        assert len(baseline.mappings) == 3

    def test_capture_baseline_from_dict(self, service):
        raw = [
            {
                "term": "diabetes",
                "concept_id": 201826,
                "concept_name": "Type 2 DM",
                "domain_id": "Condition",
                "vocabulary_id": "SNOMED",
                "standard_concept": "S",
            }
        ]

        baseline = service.capture_baseline_from_dict(
            "dict-baseline", raw, version="v5.0", persist=False
        )

        assert baseline.total_count == 1
        assert baseline.mappings[0].term == "diabetes"

    def test_get_baseline(self, service):
        mappings = [_make_mapping("test")]
        service.capture_baseline("my-baseline", mappings, persist=False)

        retrieved = service.get_baseline("my-baseline")
        assert retrieved is not None
        assert retrieved.name == "my-baseline"

    def test_get_baseline_not_found(self, service):
        result = service.get_baseline("nonexistent")
        assert result is None

    def test_list_baselines(self, service):
        service.capture_baseline("baseline-a", [_make_mapping("a")], persist=False)
        service.capture_baseline("baseline-b", [_make_mapping("b")], persist=False)

        names = service.list_baselines()
        assert "baseline-a" in names
        assert "baseline-b" in names


# ============================================================================
# Service - Change detection tests
# ============================================================================


class TestChangeDetection:
    """Test vocabulary change detection between baseline and current."""

    @pytest.fixture
    def service(self):
        return VocabRegressionService()

    def test_no_changes_detected(self, service):
        """Identical mappings should produce zero changes."""
        mappings = [
            _make_mapping("diabetes", concept_id=201826, concept_name="Type 2 DM"),
            _make_mapping("asthma", concept_id=317009, concept_name="Asthma"),
        ]

        baseline = service.capture_baseline("v1", mappings, persist=False)
        report = service.compare_against_baseline(baseline, deepcopy(mappings))

        assert report.unchanged == 2
        assert report.changed == 0
        assert report.high_risk_changes == 0
        assert len(report.changes) == 0

    def test_concept_id_change_detection(self, service):
        """Detect when a term maps to a different concept ID."""
        baseline_mappings = [
            _make_mapping("diabetes", concept_id=201826, concept_name="Type 2 DM"),
        ]
        current_mappings = [
            _make_mapping("diabetes", concept_id=999999, concept_name="Diabetes Updated"),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        id_changes = [c for c in report.changes if c.change_type == ChangeType.ID_CHANGED]
        assert len(id_changes) == 1
        assert id_changes[0].old_concept_id == 201826
        assert id_changes[0].new_concept_id == 999999

    def test_deprecation_detection(self, service):
        """Detect when a concept goes from standard to non-standard."""
        baseline_mappings = [
            _make_mapping("old drug", concept_id=100, standard_concept="S", domain_id="Drug"),
        ]
        current_mappings = [
            _make_mapping("old drug", concept_id=100, standard_concept=None, domain_id="Drug"),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        deprecations = [c for c in report.changes if c.change_type == ChangeType.DEPRECATED]
        assert len(deprecations) == 1
        assert "standard_concept=S" in deprecations[0].old_value
        assert report.deprecated_mappings >= 1

    def test_deprecation_missing_term(self, service):
        """Detect when a term is no longer present in current mappings."""
        baseline_mappings = [
            _make_mapping("removed condition", concept_id=555, domain_id="Condition"),
        ]
        current_mappings: list[VocabMapping] = []

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        deprecations = [c for c in report.changes if c.change_type == ChangeType.DEPRECATED]
        assert len(deprecations) == 1
        assert deprecations[0].term == "removed condition"

    def test_domain_change_detection(self, service):
        """Detect when a concept moves to a different domain."""
        baseline_mappings = [
            _make_mapping("fatigue", concept_id=4223659, domain_id="Condition"),
        ]
        current_mappings = [
            _make_mapping("fatigue", concept_id=4223659, domain_id="Observation"),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        domain_changes = [c for c in report.changes if c.change_type == ChangeType.DOMAIN_CHANGED]
        assert len(domain_changes) == 1
        assert domain_changes[0].old_value == "Condition"
        assert domain_changes[0].new_value == "Observation"

    def test_new_mapping_detection(self, service):
        """Detect terms that are new in current but not in baseline."""
        baseline_mappings = [
            _make_mapping("diabetes", concept_id=201826),
        ]
        current_mappings = [
            _make_mapping("diabetes", concept_id=201826),
            _make_mapping("new condition", concept_id=888888, concept_name="New Condition"),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        new_mappings = [c for c in report.changes if c.change_type == ChangeType.NEW_MAPPING]
        assert len(new_mappings) == 1
        assert new_mappings[0].term == "new condition"
        assert report.new_mappings == 1

    def test_confidence_change_detection(self, service):
        """Detect significant confidence score changes (>10%)."""
        baseline_mappings = [
            _make_mapping("ambiguous term", concept_id=100, confidence=0.95),
        ]
        current_mappings = [
            _make_mapping("ambiguous term", concept_id=100, confidence=0.70),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        confidence_changes = [
            c for c in report.changes if c.change_type == ChangeType.CONFIDENCE_CHANGED
        ]
        assert len(confidence_changes) == 1
        assert "0.950" in confidence_changes[0].old_value
        assert "0.700" in confidence_changes[0].new_value

    def test_small_confidence_change_ignored(self, service):
        """Small confidence changes (<=10%) should not be flagged."""
        baseline_mappings = [
            _make_mapping("stable term", concept_id=100, confidence=0.95),
        ]
        current_mappings = [
            _make_mapping("stable term", concept_id=100, confidence=0.90),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        confidence_changes = [
            c for c in report.changes if c.change_type == ChangeType.CONFIDENCE_CHANGED
        ]
        assert len(confidence_changes) == 0

    def test_multiple_changes_same_term(self, service):
        """A single term can have multiple change types."""
        baseline_mappings = [
            _make_mapping(
                "complex term",
                concept_id=100,
                concept_name="Old Name",
                domain_id="Condition",
                confidence=0.95,
            ),
        ]
        current_mappings = [
            _make_mapping(
                "complex term",
                concept_id=200,
                concept_name="New Name",
                domain_id="Observation",
                confidence=0.70,
            ),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        # Should detect: ID change, domain change, confidence change
        change_types = {c.change_type for c in report.changes}
        assert ChangeType.ID_CHANGED in change_types
        assert ChangeType.DOMAIN_CHANGED in change_types
        assert ChangeType.CONFIDENCE_CHANGED in change_types

    def test_case_insensitive_matching(self, service):
        """Term matching should be case-insensitive."""
        baseline_mappings = [
            _make_mapping("Type 2 Diabetes", concept_id=201826),
        ]
        current_mappings = [
            _make_mapping("type 2 diabetes", concept_id=201826),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        assert report.unchanged == 1
        assert report.changed == 0


# ============================================================================
# Service - Risk assessment tests
# ============================================================================


class TestRiskAssessment:
    """Test risk level classification for vocabulary changes."""

    @pytest.fixture
    def service(self):
        return VocabRegressionService()

    def test_high_risk_trial_critical_term(self, service):
        """Trial-critical term changes should be high risk."""
        baseline_mappings = [
            _make_mapping(
                "atopic dermatitis",
                concept_id=4182711,
                domain_id="Condition",
            ),
        ]
        current_mappings = [
            _make_mapping(
                "atopic dermatitis",
                concept_id=999999,
                domain_id="Condition",
            ),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        high_risk = service.get_high_risk_changes(report)
        assert len(high_risk) >= 1
        assert high_risk[0].risk_level == RiskLevel.HIGH
        assert report.high_risk_changes >= 1

    def test_high_risk_deprecation_in_clinical_domain(self, service):
        """Deprecation in Drug domain should be high risk."""
        baseline_mappings = [
            _make_mapping(
                "old medication",
                concept_id=100,
                domain_id="Drug",
                standard_concept="S",
            ),
        ]
        # Term removed from current
        current_mappings: list[VocabMapping] = []

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        high_risk = service.get_high_risk_changes(report)
        assert len(high_risk) >= 1

    def test_trial_impacting_changes(self, service):
        """Changes to trial-critical terms should appear in trial_impacting_changes."""
        baseline_mappings = [
            _make_mapping("diabetic macular edema", concept_id=4324190, domain_id="Condition"),
            _make_mapping("cscc", concept_id=4111921, domain_id="Condition"),
            _make_mapping("headache", concept_id=378253, domain_id="Condition"),
        ]
        current_mappings = [
            _make_mapping("diabetic macular edema", concept_id=999999, domain_id="Condition"),
            _make_mapping("cscc", concept_id=888888, domain_id="Condition"),
            _make_mapping("headache", concept_id=378253, domain_id="Condition"),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        # DME and CSCC are trial-critical, headache is not
        trial_terms = {c.term.lower() for c in report.trial_impacting_changes}
        assert "diabetic macular edema" in trial_terms
        assert "cscc" in trial_terms
        assert "headache" not in trial_terms

    def test_low_risk_new_mapping(self, service):
        """New mappings should always be low risk."""
        baseline_mappings = [_make_mapping("existing", concept_id=100)]
        current_mappings = [
            _make_mapping("existing", concept_id=100),
            _make_mapping("brand new term", concept_id=200),
        ]

        baseline = service.capture_baseline("v1", baseline_mappings, persist=False)
        report = service.compare_against_baseline(baseline, current_mappings)

        new_mappings = [c for c in report.changes if c.change_type == ChangeType.NEW_MAPPING]
        assert all(c.risk_level == RiskLevel.LOW for c in new_mappings)


# ============================================================================
# Service - Vocabulary update preview
# ============================================================================


class TestVocabularyUpdatePreview:
    """Test vocabulary update impact preview."""

    @pytest.fixture
    def service(self):
        return VocabRegressionService()

    def test_preview_safe_update(self, service):
        """Update with no changes should recommend 'safe_to_apply'."""
        mappings = [_make_mapping("diabetes", concept_id=201826)]
        service.capture_baseline("v1", mappings, persist=False)

        preview = service.preview_vocabulary_update("v1", deepcopy(mappings))
        assert preview.recommendation == "safe_to_apply"
        assert preview.breaking_changes == 0

    def test_preview_blocked_update(self, service):
        """Update with high-risk changes should recommend 'block_update'."""
        baseline_mappings = [
            _make_mapping("atopic dermatitis", concept_id=4182711, domain_id="Condition"),
        ]
        service.capture_baseline("v1", baseline_mappings, persist=False)

        updated_mappings = [
            _make_mapping("atopic dermatitis", concept_id=999999, domain_id="Condition"),
        ]
        preview = service.preview_vocabulary_update("v1", updated_mappings)
        assert preview.recommendation == "block_update"
        assert preview.breaking_changes >= 1

    def test_preview_not_found_baseline(self, service):
        """Preview with nonexistent baseline should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.preview_vocabulary_update("nonexistent", [])


# ============================================================================
# Service - Baseline serialization/deserialization
# ============================================================================


class TestBaselinePersistence:
    """Test baseline file persistence and loading."""

    def test_save_and_load_baseline(self):
        """Baselines should round-trip through JSON serialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            service = VocabRegressionService(storage_dir=storage)

            mappings = [
                _make_mapping("diabetes", concept_id=201826),
                _make_mapping("asthma", concept_id=317009),
            ]

            # Capture (saves to disk)
            service.capture_baseline("persist-test", mappings, version="v5.0")

            # Verify file exists
            assert (storage / "persist-test.json").exists()

            # Create new service and load from disk
            service2 = VocabRegressionService(storage_dir=storage)
            loaded = service2.get_baseline("persist-test")

            assert loaded is not None
            assert loaded.name == "persist-test"
            assert loaded.version == "v5.0"
            assert loaded.total_count == 2
            assert len(loaded.mappings) == 2

    def test_load_baseline_from_fixture_file(self):
        """Should be able to load the fixture baseline file."""
        service = VocabRegressionService()
        baseline = service.load_baseline_from_file(FIXTURE_PATH)

        assert baseline.name == "omop-v5.0-baseline"
        assert baseline.version == "v5.0-2026-01"
        assert len(baseline.mappings) >= 500

    def test_load_nonexistent_file(self):
        """Loading a nonexistent file should raise FileNotFoundError."""
        service = VocabRegressionService()
        with pytest.raises(FileNotFoundError):
            service.load_baseline_from_file(Path("/nonexistent/file.json"))


# ============================================================================
# Service - Fixture integration tests
# ============================================================================


class TestFixtureIntegration:
    """Test with the 500+ entry fixture file."""

    @pytest.fixture
    def service(self):
        return VocabRegressionService()

    @pytest.fixture
    def fixture_baseline(self, service):
        return service.load_baseline_from_file(FIXTURE_PATH)

    @pytest.fixture
    def fixture_mappings(self):
        return _load_fixture_mappings()

    def test_fixture_has_500_plus_entries(self, fixture_baseline):
        """The fixture should have 500+ mappings."""
        assert len(fixture_baseline.mappings) >= 500

    def test_fixture_covers_conditions(self, fixture_baseline):
        """The fixture should cover common conditions."""
        terms = {m.term.lower() for m in fixture_baseline.mappings}
        assert "type 2 diabetes mellitus" in terms
        assert "hypertension" in terms
        assert "asthma" in terms
        assert "heart failure" in terms
        assert "breast cancer" in terms

    def test_fixture_covers_medications(self, fixture_baseline):
        """The fixture should cover common medications."""
        terms = {m.term.lower() for m in fixture_baseline.mappings}
        assert "metformin" in terms
        assert "aspirin" in terms
        assert "lisinopril" in terms
        assert "atorvastatin" in terms
        assert "insulin" in terms

    def test_fixture_covers_labs(self, fixture_baseline):
        """The fixture should cover common lab measurements."""
        terms = {m.term.lower() for m in fixture_baseline.mappings}
        assert "hemoglobin a1c" in terms
        assert "serum creatinine" in terms
        assert "egfr" in terms
        assert "total cholesterol" in terms

    def test_fixture_covers_trial_terms(self, fixture_baseline):
        """The fixture should cover trial-relevant terms."""
        terms = {m.term.lower() for m in fixture_baseline.mappings}
        assert "diabetic macular edema" in terms
        assert "dme" in terms
        assert "atopic dermatitis" in terms
        assert "cscc" in terms

    def test_no_changes_when_identical(self, service, fixture_baseline, fixture_mappings):
        """Comparing identical data should produce no changes."""
        report = service.compare_against_baseline(fixture_baseline, fixture_mappings)
        assert report.unchanged == len(fixture_mappings)
        assert report.changed == 0
        assert report.high_risk_changes == 0

    def test_simulated_vocabulary_update(self, service, fixture_baseline, fixture_mappings):
        """Simulate a vocabulary update affecting multiple terms."""
        updated = deepcopy(fixture_mappings)

        # Simulate: change concept_id for diabetes
        for m in updated:
            if m.term.lower() == "type 2 diabetes mellitus":
                m.concept_id = 999999
                m.concept_name = "Type 2 DM (Updated)"
                break

        # Simulate: deprecate an asthma concept
        for m in updated:
            if m.term.lower() == "asthma":
                m.standard_concept = None
                break

        # Simulate: domain change for a measurement
        for m in updated:
            if m.term.lower() == "hemoglobin a1c":
                m.domain_id = "Observation"
                break

        report = service.compare_against_baseline(fixture_baseline, updated)

        assert report.changed > 0
        change_types = {c.change_type for c in report.changes}
        assert ChangeType.ID_CHANGED in change_types
        assert ChangeType.DEPRECATED in change_types
        assert ChangeType.DOMAIN_CHANGED in change_types


# ============================================================================
# Singleton tests
# ============================================================================


class TestVocabRegressionServiceSingleton:
    """Test service singleton management."""

    def test_get_returns_same_instance(self):
        reset_vocab_regression_service()
        svc1 = get_vocab_regression_service()
        svc2 = get_vocab_regression_service()
        assert svc1 is svc2

    def test_reset_clears_singleton(self):
        reset_vocab_regression_service()
        svc1 = get_vocab_regression_service()
        reset_vocab_regression_service()
        svc2 = get_vocab_regression_service()
        assert svc1 is not svc2
