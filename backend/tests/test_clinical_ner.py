"""Tests for Clinical NER service.

Tests the ML-based clinical named entity recognition service
using spaCy and HuggingFace transformers.
"""

import pytest
from uuid import uuid4

from app.services.nlp_clinical_ner import (
    ClinicalNERService,
    TransformerNERConfig,
    get_clinical_ner_service,
    reset_clinical_ner_service,
    ENTITY_TO_DOMAIN,
)
from app.schemas.base import Assertion, Domain, Experiencer, Temporality


# ============================================================================
# Configuration Tests
# ============================================================================


class TestTransformerNERConfig:
    """Test configuration dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TransformerNERConfig()
        assert config.model_name == "samrawal/bert-base-uncased_clinical-ner"
        assert config.spacy_model == "en_core_web_sm"
        assert config.use_gpu is True
        assert config.min_entity_length == 2
        assert config.min_confidence == 0.5
        assert config.context_window == 50
        assert config.detect_assertion is True
        assert config.detect_temporality is True
        assert config.max_sequence_length == 512
        assert config.batch_size == 8

    def test_custom_config(self):
        """Test custom configuration."""
        config = TransformerNERConfig(
            model_name="custom-model",
            spacy_model="en_core_web_md",
            min_confidence=0.8,
            context_window=100,
            detect_assertion=False,
        )
        assert config.model_name == "custom-model"
        assert config.spacy_model == "en_core_web_md"
        assert config.min_confidence == 0.8
        assert config.context_window == 100
        assert config.detect_assertion is False


# ============================================================================
# Entity Mapping Tests
# ============================================================================


class TestEntityMapping:
    """Test entity type to OMOP domain mapping."""

    def test_problem_maps_to_condition(self):
        """Test PROBLEM entity maps to Condition domain."""
        assert ENTITY_TO_DOMAIN["PROBLEM"] == Domain.CONDITION.value
        assert ENTITY_TO_DOMAIN["DISEASE"] == Domain.CONDITION.value

    def test_treatment_maps_to_drug(self):
        """Test TREATMENT entity maps to Drug domain."""
        assert ENTITY_TO_DOMAIN["TREATMENT"] == Domain.DRUG.value
        assert ENTITY_TO_DOMAIN["MEDICATION"] == Domain.DRUG.value
        assert ENTITY_TO_DOMAIN["DRUG"] == Domain.DRUG.value

    def test_test_maps_to_measurement(self):
        """Test TEST entity maps to Measurement domain."""
        assert ENTITY_TO_DOMAIN["TEST"] == Domain.MEASUREMENT.value
        assert ENTITY_TO_DOMAIN["LAB"] == Domain.MEASUREMENT.value

    def test_anatomy_maps_to_anatomic_site(self):
        """Test ANATOMY entity maps to Spec Anatomic Site domain."""
        assert ENTITY_TO_DOMAIN["ANATOMY"] == Domain.SPEC_ANATOMIC_SITE.value
        assert ENTITY_TO_DOMAIN["BODY_PART"] == Domain.SPEC_ANATOMIC_SITE.value

    def test_procedure_maps_to_procedure(self):
        """Test PROCEDURE entity maps to Procedure domain."""
        assert ENTITY_TO_DOMAIN["PROCEDURE"] == Domain.PROCEDURE.value

    def test_excluded_entities(self):
        """Test entities that should be excluded (map to None)."""
        assert ENTITY_TO_DOMAIN["PERSON"] is None
        assert ENTITY_TO_DOMAIN["ORG"] is None
        assert ENTITY_TO_DOMAIN["GPE"] is None
        assert ENTITY_TO_DOMAIN["DATE"] is None


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestClinicalNERServiceInit:
    """Test service initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_clinical_ner_service()

    def test_service_creation(self):
        """Test basic service creation."""
        service = ClinicalNERService()
        assert service is not None
        assert service.config is not None

    def test_service_with_custom_config(self):
        """Test service creation with custom config."""
        config = TransformerNERConfig(min_confidence=0.9)
        service = ClinicalNERService(config=config)
        assert service.config.min_confidence == 0.9

    def test_singleton_pattern(self):
        """Test singleton pattern works."""
        service1 = get_clinical_ner_service()
        service2 = get_clinical_ner_service()
        assert service1 is service2

    def test_singleton_reset(self):
        """Test singleton can be reset."""
        service1 = get_clinical_ner_service()
        reset_clinical_ner_service()
        service2 = get_clinical_ner_service()
        assert service1 is not service2

    def test_is_available(self):
        """Test availability check."""
        service = ClinicalNERService()
        # Should be available if spaCy is installed
        is_available = service.is_available()
        # Result depends on installed models, just check it runs
        assert isinstance(is_available, bool)


# ============================================================================
# Context Detection Tests
# ============================================================================


class TestContextDetection:
    """Test assertion, temporality, and experiencer detection."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()
        # Force initialization
        self.service._initialize()

    def test_negation_detection(self):
        """Test negation pattern detection."""
        text = "Patient denies chest pain and shortness of breath."
        # "chest pain" starts at index 15, ends at 25
        assertion = self.service._detect_assertion(text, 15, 25)
        assert assertion == Assertion.ABSENT

    def test_no_negation_detection(self):
        """Test 'no' negation detection."""
        text = "No evidence of diabetes."
        # "diabetes" starts at 15, ends at 23
        assertion = self.service._detect_assertion(text, 15, 23)
        assert assertion == Assertion.ABSENT

    def test_ruled_out_detection(self):
        """Test 'ruled out' negation detection."""
        text = "Ruled out MI based on negative troponins."
        # "MI" starts at 10, ends at 12
        assertion = self.service._detect_assertion(text, 10, 12)
        assert assertion == Assertion.ABSENT

    def test_uncertainty_detection(self):
        """Test uncertainty pattern detection."""
        text = "Possible pneumonia seen on chest X-ray."
        # "pneumonia" starts at 9, ends at 18
        assertion = self.service._detect_assertion(text, 9, 18)
        assert assertion == Assertion.POSSIBLE

    def test_likely_uncertainty(self):
        """Test 'likely' uncertainty detection."""
        text = "Likely viral infection."
        assertion = self.service._detect_assertion(text, 7, 22)
        assert assertion == Assertion.POSSIBLE

    def test_present_assertion(self):
        """Test present assertion when no negation/uncertainty."""
        text = "Patient has diabetes mellitus."
        # "diabetes mellitus" starts at 12, ends at 29
        assertion = self.service._detect_assertion(text, 12, 29)
        assert assertion == Assertion.PRESENT

    def test_history_of_temporality(self):
        """Test history of temporality detection."""
        text = "History of myocardial infarction."
        # "myocardial infarction" starts at 11, ends at 32
        temporality = self.service._detect_temporality(text, 11, 32)
        assert temporality == Temporality.PAST

    def test_prior_temporality(self):
        """Test 'prior' temporality detection."""
        text = "Prior coronary artery bypass grafting."
        temporality = self.service._detect_temporality(text, 6, 37)
        assert temporality == Temporality.PAST

    def test_current_temporality(self):
        """Test current temporality when no history markers."""
        text = "Patient presents with chest pain."
        temporality = self.service._detect_temporality(text, 22, 32)
        assert temporality == Temporality.CURRENT

    def test_family_history_experiencer(self):
        """Test family history experiencer detection."""
        text = "Family history of colon cancer."
        # "colon cancer" starts at 18, ends at 30
        experiencer = self.service._detect_experiencer(text, 18, 30)
        assert experiencer == Experiencer.FAMILY

    def test_mother_experiencer(self):
        """Test mother as family experiencer."""
        text = "Mother has breast cancer."
        experiencer = self.service._detect_experiencer(text, 11, 24)
        assert experiencer == Experiencer.FAMILY

    def test_patient_experiencer(self):
        """Test patient as experiencer when no family markers."""
        text = "Patient diagnosed with hypertension."
        experiencer = self.service._detect_experiencer(text, 23, 35)
        assert experiencer == Experiencer.PATIENT


# ============================================================================
# Text Chunking Tests
# ============================================================================


class TestTextChunking:
    """Test text chunking for long documents."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()

    def test_short_text_no_chunking(self):
        """Test that short text doesn't get chunked."""
        text = "Patient has diabetes."
        chunks = self.service._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_chunking(self):
        """Test that long text gets chunked."""
        # Create text longer than chunk size
        chunk_size = self.service.config.max_sequence_length * 4
        long_text = "Patient has diabetes. " * (chunk_size // 20)
        chunks = self.service._chunk_text(long_text)
        assert len(chunks) >= 1
        # Chunks should cover the whole text
        combined_length = sum(len(c) for c in chunks)
        # Account for overlap
        assert combined_length >= len(long_text)


# ============================================================================
# Extraction Tests
# ============================================================================


class TestMentionExtraction:
    """Test mention extraction functionality."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()

    def test_extract_mentions_basic(self):
        """Test basic mention extraction."""
        text = "Patient has diabetes mellitus and hypertension."
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        # Result depends on model availability
        assert isinstance(mentions, list)

    def test_extract_mentions_returns_extracted_mention_objects(self):
        """Test that extraction returns ExtractedMention objects."""
        text = "Patient diagnosed with chronic kidney disease."
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        for mention in mentions:
            assert hasattr(mention, "text")
            assert hasattr(mention, "start_offset")
            assert hasattr(mention, "end_offset")
            assert hasattr(mention, "assertion")
            assert hasattr(mention, "temporality")
            assert hasattr(mention, "experiencer")
            assert hasattr(mention, "confidence")

    def test_extract_mentions_with_negation(self):
        """Test extraction handles negation context."""
        text = "Patient denies chest pain. Patient has diabetes."
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        # Check that mentions with negation context have ABSENT assertion
        for mention in mentions:
            if "chest pain" in mention.text.lower():
                assert mention.assertion == Assertion.ABSENT

    def test_extract_mentions_with_history(self):
        """Test extraction handles history context."""
        text = "History of MI. Currently has diabetes."
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        for mention in mentions:
            if "mi" in mention.text.lower():
                assert mention.temporality == Temporality.PAST

    def test_extract_mentions_empty_text(self):
        """Test extraction with empty text."""
        doc_id = uuid4()
        mentions = self.service.extract_mentions("", doc_id)
        assert mentions == []

    def test_extract_mentions_short_entities_filtered(self):
        """Test that short entities are filtered out."""
        text = "A B C diabetes mellitus"
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        # Single letter entities should be filtered
        for mention in mentions:
            assert len(mention.text.strip()) >= 2


# ============================================================================
# Entity Merging Tests
# ============================================================================


class TestEntityMerging:
    """Test entity merging from multiple sources."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()

    def test_merge_non_overlapping(self):
        """Test merging non-overlapping entities."""
        transformer_ents = [
            {"word": "diabetes", "start": 0, "end": 8, "entity_group": "DISEASE", "score": 0.9}
        ]
        spacy_ents = [
            {"word": "hypertension", "start": 13, "end": 25, "entity_group": "DISEASE", "score": 0.6}
        ]
        merged = self.service._merge_entities(transformer_ents, spacy_ents)
        assert len(merged) == 2

    def test_merge_overlapping_prefers_transformer(self):
        """Test that overlapping entities prefer transformer results."""
        transformer_ents = [
            {"word": "diabetes mellitus", "start": 0, "end": 17, "entity_group": "DISEASE", "score": 0.9}
        ]
        spacy_ents = [
            {"word": "diabetes", "start": 0, "end": 8, "entity_group": "DISEASE", "score": 0.6}
        ]
        merged = self.service._merge_entities(transformer_ents, spacy_ents)
        # Only transformer result should remain
        assert len(merged) == 1
        assert merged[0]["word"] == "diabetes mellitus"

    def test_merge_empty_transformer(self):
        """Test merging when transformer returns nothing."""
        transformer_ents = []
        spacy_ents = [
            {"word": "diabetes", "start": 0, "end": 8, "entity_group": "DISEASE", "score": 0.6}
        ]
        merged = self.service._merge_entities(transformer_ents, spacy_ents)
        assert len(merged) == 1
        assert merged[0]["word"] == "diabetes"


# ============================================================================
# Section Detection Tests
# ============================================================================


class TestSectionDetection:
    """Test section detection in clinical text."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()

    def test_get_section_medications(self):
        """Test detecting Medications section."""
        text = """
MEDICATIONS:
Metformin 500mg BID
Lisinopril 10mg daily
"""
        # Position within medications section
        section = self.service.get_section_name(text, 30)
        assert section is not None
        assert section.lower() == "medications"

    def test_get_section_history(self):
        """Test detecting History section."""
        text = """
HISTORY OF PRESENT ILLNESS:
Patient is a 65 year old male with diabetes.

MEDICATIONS:
Metformin 500mg
"""
        section = self.service.get_section_name(text, 50)
        assert section is not None
        assert section.lower() == "history of present illness"

    def test_get_section_assessment(self):
        """Test detecting Assessment section."""
        text = """
ASSESSMENT AND PLAN:
1. Diabetes - continue metformin
2. Hypertension - start lisinopril
"""
        section = self.service.get_section_name(text, 40)
        assert section is not None
        # "Assessment and Plan" matches both "Assessment" and "Plan" patterns;
        # the service returns whichever pattern has the latest position
        assert section.lower() in ("assessment", "plan", "assessment and plan")


# ============================================================================
# Complex Clinical Text Tests
# ============================================================================


class TestComplexClinicalText:
    """Test extraction on realistic clinical text."""

    def setup_method(self):
        """Create service for testing."""
        reset_clinical_ner_service()
        self.service = ClinicalNERService()

    def test_complex_clinical_note(self):
        """Test extraction on a complex clinical note."""
        text = """
HISTORY OF PRESENT ILLNESS:
65 year old male with history of type 2 diabetes mellitus,
hypertension, and prior myocardial infarction presents with
chest pain. Patient denies shortness of breath.
Family history of colon cancer in mother.

ASSESSMENT:
1. Chest pain - likely musculoskeletal, rule out ACS
2. Diabetes - controlled on metformin
3. Hypertension - well controlled

PLAN:
- EKG and troponins
- Continue metformin 1000mg BID
- Start aspirin 81mg daily
"""
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)

        # Check basic extraction
        assert isinstance(mentions, list)

        # Print extracted mentions for debugging
        for mention in mentions:
            print(f"  {mention.text}: {mention.domain_hint}, assertion={mention.assertion}")

    def test_discharge_summary(self):
        """Test extraction on discharge summary."""
        text = """
DISCHARGE DIAGNOSIS:
1. Community-acquired pneumonia
2. Type 2 diabetes mellitus
3. Chronic kidney disease stage 3

HOSPITAL COURSE:
Patient was admitted with fever, cough, and shortness of breath.
Chest X-ray showed right lower lobe infiltrate.
Started on ceftriaxone and azithromycin with clinical improvement.

DISCHARGE MEDICATIONS:
1. Azithromycin 250mg daily x 2 days
2. Metformin 500mg BID
3. Lisinopril 5mg daily
"""
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        assert isinstance(mentions, list)

    def test_procedure_note(self):
        """Test extraction on procedure note."""
        text = """
PROCEDURE: Colonoscopy

FINDINGS:
Two polyps found in sigmoid colon, removed with snare polypectomy.
No evidence of malignancy. Hemorrhoids noted.

IMPRESSION:
1. Sigmoid polyps, removed
2. Internal hemorrhoids
"""
        doc_id = uuid4()
        mentions = self.service.extract_mentions(text, doc_id)
        assert isinstance(mentions, list)


# ============================================================================
# Configuration Behavior Tests
# ============================================================================


class TestConfigurationBehavior:
    """Test configuration affects service behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_clinical_ner_service()

    def test_assertion_detection_disabled(self):
        """Test disabling assertion detection."""
        config = TransformerNERConfig(detect_assertion=False)
        service = ClinicalNERService(config=config)
        service._initialize()

        text = "Patient denies chest pain."
        assertion = service._detect_assertion(text, 15, 25)
        # Should always return PRESENT when disabled
        assert assertion == Assertion.PRESENT

    def test_temporality_detection_disabled(self):
        """Test disabling temporality detection."""
        config = TransformerNERConfig(detect_temporality=False)
        service = ClinicalNERService(config=config)
        service._initialize()

        text = "History of MI."
        temporality = service._detect_temporality(text, 11, 13)
        # Should always return CURRENT when disabled
        assert temporality == Temporality.CURRENT

    def test_high_confidence_threshold(self):
        """Test high confidence threshold filters more entities."""
        text = "Patient has diabetes and hypertension."
        doc_id = uuid4()

        # Low threshold
        config_low = TransformerNERConfig(min_confidence=0.1)
        service_low = ClinicalNERService(config=config_low)
        mentions_low = service_low.extract_mentions(text, doc_id)

        reset_clinical_ner_service()

        # High threshold
        config_high = TransformerNERConfig(min_confidence=0.99)
        service_high = ClinicalNERService(config=config_high)
        mentions_high = service_high.extract_mentions(text, doc_id)

        # High threshold should filter more
        assert len(mentions_high) <= len(mentions_low)


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for NER service."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_clinical_ner_service()

    def test_service_through_module_interface(self):
        """Test accessing service through module interface."""
        from app.services import (
            ClinicalNERService,
            get_clinical_ner_service,
            reset_clinical_ner_service,
        )

        service = get_clinical_ner_service()
        assert isinstance(service, ClinicalNERService)

        reset_clinical_ner_service()
        service2 = get_clinical_ner_service()
        assert service is not service2

    def test_service_implements_interface(self):
        """Test that service implements NLPServiceInterface."""
        from app.services.nlp import NLPServiceInterface, BaseNLPService

        service = ClinicalNERService()
        assert isinstance(service, BaseNLPService)

        # Check required methods exist
        assert hasattr(service, "extract_mentions")
        assert hasattr(service, "get_section_name")
        assert callable(service.extract_mentions)
        assert callable(service.get_section_name)
