"""Contract tests for NLP canonicalization (Phase 2).

Verifies:
- Singleton accessors return correct types
- nlp_entity_service.py re-exports match nlp_entity/__init__.py
- nlp_shared canonical lists are non-empty and match authoritative copies
- Smoke tests for extraction paths
"""

from __future__ import annotations

import importlib

import pytest


# ============================================================================
# 1. get_nlp_entity_service() returns an NLPServiceInterface implementor
# ============================================================================


def test_get_nlp_entity_service_returns_interface_implementor():
    """get_nlp_entity_service() should return an object whose class
    is a subclass of or structurally compatible with NLPServiceInterface
    (i.e. it has an extract_entities method).
    """
    from app.services.nlp_entity import get_nlp_entity_service

    service = get_nlp_entity_service()
    # ClinicalNLPEntityService is not a subclass of NLPServiceInterface
    # (it uses a different interface), but it must have extract_entities.
    assert hasattr(service, "extract_entities"), (
        "get_nlp_entity_service() must return an object with extract_entities()"
    )
    assert callable(service.extract_entities)


def test_get_nlp_entity_service_singleton():
    """Repeated calls should return the same singleton instance."""
    from app.services.nlp_entity import get_nlp_entity_service

    a = get_nlp_entity_service()
    b = get_nlp_entity_service()
    assert a is b


# ============================================================================
# 2. get_ensemble_nlp_service() returns a BaseNLPService subclass
# ============================================================================


def test_get_ensemble_nlp_service_returns_base_nlp_subclass():
    """get_ensemble_nlp_service() should return a BaseNLPService subclass."""
    from app.services.nlp import BaseNLPService
    from app.services.nlp_ensemble import get_ensemble_nlp_service

    service = get_ensemble_nlp_service()
    assert isinstance(service, BaseNLPService), (
        f"Expected BaseNLPService subclass, got {type(service).__name__}"
    )


# ============================================================================
# 3. nlp_entity_service.py re-exports match nlp_entity/__init__.py
# ============================================================================


def test_nlp_entity_service_reexports_match_init():
    """Every name in nlp_entity/__init__.__all__ must also appear in
    nlp_entity_service.__all__ (backwards-compatibility shim).
    """
    import app.services.nlp_entity as pkg_init
    import app.services.nlp_entity_service as compat_shim

    pkg_all = set(pkg_init.__all__)
    shim_all = set(compat_shim.__all__)

    missing = pkg_all - shim_all
    assert not missing, (
        f"nlp_entity_service.py is missing re-exports for: {missing}"
    )


def test_nlp_entity_service_reexports_are_same_objects():
    """Re-exported names should reference the exact same objects."""
    import app.services.nlp_entity as pkg_init
    import app.services.nlp_entity_service as compat_shim

    for name in pkg_init.__all__:
        pkg_obj = getattr(pkg_init, name)
        shim_obj = getattr(compat_shim, name, None)
        assert shim_obj is not None, (
            f"{name} not found in nlp_entity_service.py"
        )
        assert shim_obj is pkg_obj, (
            f"{name} in nlp_entity_service.py is not the same object as in nlp_entity/__init__.py"
        )


# ============================================================================
# 4. nlp_shared canonical lists are non-empty and match authoritative copy
# ============================================================================


def test_canonical_negation_triggers_non_empty():
    """CANONICAL_NEGATION_TRIGGERS must be a non-empty list."""
    from app.services.nlp_shared import CANONICAL_NEGATION_TRIGGERS

    assert isinstance(CANONICAL_NEGATION_TRIGGERS, list)
    assert len(CANONICAL_NEGATION_TRIGGERS) > 0


def test_canonical_negation_triggers_match_authoritative():
    """CANONICAL_NEGATION_TRIGGERS must exactly match the authoritative
    copy in nlp_entity_normalizers.NEGATION_TRIGGERS.
    """
    from app.services.nlp_shared import CANONICAL_NEGATION_TRIGGERS
    from app.services.nlp_entity.nlp_entity_normalizers import NEGATION_TRIGGERS

    assert CANONICAL_NEGATION_TRIGGERS == NEGATION_TRIGGERS, (
        "nlp_shared.CANONICAL_NEGATION_TRIGGERS has diverged from "
        "nlp_entity_normalizers.NEGATION_TRIGGERS"
    )


def test_canonical_section_headers_non_empty():
    """CANONICAL_SECTION_HEADERS must be a non-empty dict."""
    from app.services.nlp_shared import CANONICAL_SECTION_HEADERS

    assert isinstance(CANONICAL_SECTION_HEADERS, dict)
    assert len(CANONICAL_SECTION_HEADERS) > 0


def test_canonical_section_headers_keys_match():
    """CANONICAL_SECTION_HEADERS keys should match ClinicalSection enum values
    from nlp_entity_normalizers.SECTION_PATTERNS.
    """
    from app.services.nlp_shared import CANONICAL_SECTION_HEADERS
    from app.services.nlp_entity.nlp_entity_normalizers import (
        SECTION_PATTERNS,
        ClinicalSection,
    )

    authoritative_keys = {section.value for section in SECTION_PATTERNS}
    canonical_keys = set(CANONICAL_SECTION_HEADERS.keys())
    assert canonical_keys == authoritative_keys, (
        f"Key mismatch — missing: {authoritative_keys - canonical_keys}, "
        f"extra: {canonical_keys - authoritative_keys}"
    )


def test_canonical_section_headers_patterns_match():
    """CANONICAL_SECTION_HEADERS pattern lists should match SECTION_PATTERNS."""
    from app.services.nlp_shared import CANONICAL_SECTION_HEADERS
    from app.services.nlp_entity.nlp_entity_normalizers import (
        SECTION_PATTERNS,
    )

    for section_enum, patterns in SECTION_PATTERNS.items():
        key = section_enum.value
        assert key in CANONICAL_SECTION_HEADERS, f"Missing section key: {key}"
        assert CANONICAL_SECTION_HEADERS[key] == patterns, (
            f"Pattern mismatch for section '{key}'"
        )


def test_canonical_uncertainty_triggers_non_empty():
    """CANONICAL_UNCERTAINTY_TRIGGERS must be non-empty and match authoritative."""
    from app.services.nlp_shared import CANONICAL_UNCERTAINTY_TRIGGERS
    from app.services.nlp_entity.nlp_entity_normalizers import UNCERTAINTY_TRIGGERS

    assert isinstance(CANONICAL_UNCERTAINTY_TRIGGERS, list)
    assert len(CANONICAL_UNCERTAINTY_TRIGGERS) > 0
    assert CANONICAL_UNCERTAINTY_TRIGGERS == UNCERTAINTY_TRIGGERS


def test_canonical_family_history_triggers_non_empty():
    """CANONICAL_FAMILY_HISTORY_TRIGGERS must be non-empty and match authoritative."""
    from app.services.nlp_shared import CANONICAL_FAMILY_HISTORY_TRIGGERS
    from app.services.nlp_entity.nlp_entity_normalizers import FAMILY_HISTORY_TRIGGERS

    assert isinstance(CANONICAL_FAMILY_HISTORY_TRIGGERS, list)
    assert len(CANONICAL_FAMILY_HISTORY_TRIGGERS) > 0
    assert CANONICAL_FAMILY_HISTORY_TRIGGERS == FAMILY_HISTORY_TRIGGERS


# ============================================================================
# 5. Smoke tests for extraction paths
# ============================================================================


def test_rule_based_extraction_smoke():
    """Rule-based extraction should return entities for a simple clinical note."""
    from app.services.nlp_entity import get_nlp_entity_service

    service = get_nlp_entity_service()
    result = service.extract_entities(
        "Patient has diabetes and hypertension. Denies chest pain."
    )

    assert result is not None
    assert result.model_id == "rule_based"
    assert result.text_length > 0
    assert result.processing_time_ms >= 0

    # Should find at least some entities
    assert len(result.entities) > 0, (
        "Rule-based extraction should find entities in a simple clinical note"
    )


def test_rule_based_negation_detection_smoke():
    """Negation detection should mark 'chest pain' as absent when preceded by 'Denies'."""
    from app.services.nlp_entity import get_nlp_entity_service
    from app.services.nlp_entity.nlp_entity_normalizers import AssertionStatus

    service = get_nlp_entity_service()
    result = service.extract_entities("Denies chest pain.")

    # Find any entity that was negated
    negated = [e for e in result.entities if e.assertion == AssertionStatus.ABSENT]
    # We expect at least one entity to be flagged as absent
    assert len(negated) > 0, (
        "Negation detection should flag entities after 'Denies' as ABSENT"
    )


def test_nlp_shared_module_importable():
    """nlp_shared should be importable as a standalone module."""
    mod = importlib.import_module("app.services.nlp_shared")
    assert hasattr(mod, "CANONICAL_NEGATION_TRIGGERS")
    assert hasattr(mod, "CANONICAL_SECTION_HEADERS")
    assert hasattr(mod, "CANONICAL_UNCERTAINTY_TRIGGERS")
    assert hasattr(mod, "CANONICAL_FAMILY_HISTORY_TRIGGERS")
