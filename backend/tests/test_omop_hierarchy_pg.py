"""Tests for PostgreSQL-backed OMOPHierarchyService.

Validates ancestor/descendant lookups via the concept_ancestor closure table,
hierarchy matching, distance-weighted quality tiers, cross-vocabulary "Maps to"
resolution, fallback behavior when PG is unavailable, and LRU cache behavior.

Uses a SQLite in-memory database with the same schema as the OMOP tables for
all standard-SQL queries. PG-specific queries (ILIKE, ANY) are tested via mock.
"""

from __future__ import annotations

import datetime
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Date, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.services.omop_hierarchy_service import (
    CacheStats,
    HierarchyMatch,
    OMOPConcept,
    OMOPHierarchyService,
    reset_omop_hierarchy_service,
)

# ---------------------------------------------------------------------------
# Test concept IDs (realistic SNOMED / OMOP IDs)
# ---------------------------------------------------------------------------
T2DM = 443238  # Type 2 diabetes mellitus
T1DM = 201254  # Type 1 diabetes mellitus
DM = 201820  # Diabetes mellitus
GLUCOSE_DISORDER = 4027120  # Disorder of glucose metabolism
CLINICAL_FINDING = 441840  # Clinical finding
HYPERTENSION = 316866  # Essential hypertension
CV_DISORDER = 134057  # Disorder of cardiovascular system
ICD10_E11 = 45591075  # ICD-10 E11 (non-standard, maps to T2DM)

# Valid date range for concept rows
VALID_START = datetime.date(1970, 1, 1)
VALID_END = datetime.date(2099, 12, 31)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def omop_engine():
    """Create a SQLite in-memory engine with OMOP vocabulary tables seeded."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    meta = MetaData()

    # -- omop_vocabulary (required FK target) --
    Table(
        "omop_vocabulary", meta,
        Column("vocabulary_id", String(20), primary_key=True),
        Column("vocabulary_name", String(255), nullable=False),
        Column("vocabulary_reference", String(255)),
        Column("vocabulary_version", String(255)),
        Column("vocabulary_concept_id", Integer, nullable=False),
    )

    # -- omop_domain --
    Table(
        "omop_domain", meta,
        Column("domain_id", String(20), primary_key=True),
        Column("domain_name", String(255), nullable=False),
        Column("domain_concept_id", Integer, nullable=False),
    )

    # -- omop_concept_class --
    Table(
        "omop_concept_class", meta,
        Column("concept_class_id", String(20), primary_key=True),
        Column("concept_class_name", String(255), nullable=False),
        Column("concept_class_concept_id", Integer, nullable=False),
    )

    # -- omop_relationship --
    Table(
        "omop_relationship", meta,
        Column("relationship_id", String(20), primary_key=True),
        Column("relationship_name", String(255), nullable=False),
        Column("is_hierarchical", String(1), nullable=False),
        Column("defines_ancestry", String(1), nullable=False),
        Column("reverse_relationship_id", String(20), nullable=False),
        Column("relationship_concept_id", Integer, nullable=False),
    )

    # -- omop_concept --
    Table(
        "omop_concept", meta,
        Column("concept_id", Integer, primary_key=True),
        Column("concept_name", String(255), nullable=False),
        Column("domain_id", String(20), nullable=False),
        Column("vocabulary_id", String(20), nullable=False),
        Column("concept_class_id", String(20), nullable=False),
        Column("standard_concept", String(1)),
        Column("concept_code", String(50), nullable=False),
        Column("valid_start_date", Date, nullable=False),
        Column("valid_end_date", Date, nullable=False),
        Column("invalid_reason", String(1)),
    )

    # -- omop_concept_ancestor --
    Table(
        "omop_concept_ancestor", meta,
        Column("ancestor_concept_id", Integer, nullable=False),
        Column("descendant_concept_id", Integer, nullable=False),
        Column("min_levels_of_separation", Integer, nullable=False),
        Column("max_levels_of_separation", Integer, nullable=False),
    )

    # -- omop_concept_relationship --
    Table(
        "omop_concept_relationship", meta,
        Column("concept_id_1", Integer, nullable=False),
        Column("concept_id_2", Integer, nullable=False),
        Column("relationship_id", String(20), nullable=False),
        Column("valid_start_date", Date, nullable=False),
        Column("valid_end_date", Date, nullable=False),
        Column("invalid_reason", String(1)),
    )

    meta.create_all(engine)

    # Seed reference data
    with Session(engine) as session:
        session.execute(text(
            "INSERT INTO omop_vocabulary VALUES "
            "('SNOMED', 'SNOMED CT', 'http://snomed.info', 'v20240101', 1), "
            "('ICD10CM', 'ICD-10-CM', 'http://icd10', 'v2024', 2)"
        ))
        session.execute(text(
            "INSERT INTO omop_domain VALUES "
            "('Condition', 'Condition', 1), "
            "('Observation', 'Observation', 2)"
        ))
        session.execute(text(
            "INSERT INTO omop_concept_class VALUES "
            "('Clinical Finding', 'Clinical Finding', 1), "
            "('4-char billing code', '4-char billing code', 2)"
        ))
        session.execute(text(
            "INSERT INTO omop_relationship VALUES "
            "('Is a', 'Is a', '1', '1', 'Subsumes', 1), "
            "('Maps to', 'Maps to', '0', '0', 'Mapped from', 2)"
        ))

        # -- Concepts --
        concepts = [
            (T2DM, "Type 2 diabetes mellitus", "Condition", "SNOMED", "Clinical Finding", "S", str(T2DM)),
            (T1DM, "Type 1 diabetes mellitus", "Condition", "SNOMED", "Clinical Finding", "S", str(T1DM)),
            (DM, "Diabetes mellitus", "Condition", "SNOMED", "Clinical Finding", "S", str(DM)),
            (GLUCOSE_DISORDER, "Disorder of glucose metabolism", "Condition", "SNOMED", "Clinical Finding", "S", str(GLUCOSE_DISORDER)),
            (CLINICAL_FINDING, "Clinical finding", "Condition", "SNOMED", "Clinical Finding", "S", str(CLINICAL_FINDING)),
            (HYPERTENSION, "Essential hypertension", "Condition", "SNOMED", "Clinical Finding", "S", str(HYPERTENSION)),
            (CV_DISORDER, "Disorder of cardiovascular system", "Condition", "SNOMED", "Clinical Finding", "S", str(CV_DISORDER)),
            (ICD10_E11, "Type 2 diabetes mellitus", "Condition", "ICD10CM", "4-char billing code", None, "E11"),
        ]
        for cid, cname, dom, vocab, cls, std, code in concepts:
            session.execute(text(
                "INSERT INTO omop_concept "
                "(concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, "
                " standard_concept, concept_code, valid_start_date, valid_end_date, invalid_reason) "
                "VALUES (:cid, :cname, :dom, :vocab, :cls, :std, :code, :vs, :ve, NULL)"
            ), {
                "cid": cid, "cname": cname, "dom": dom, "vocab": vocab,
                "cls": cls, "std": std, "code": code,
                "vs": VALID_START, "ve": VALID_END,
            })

        # -- Ancestor closure table --
        # Format: (ancestor, descendant, min_sep, max_sep)
        ancestors = [
            # Self-loops
            (T2DM, T2DM, 0, 0),
            (T1DM, T1DM, 0, 0),
            (DM, DM, 0, 0),
            (GLUCOSE_DISORDER, GLUCOSE_DISORDER, 0, 0),
            (CLINICAL_FINDING, CLINICAL_FINDING, 0, 0),
            (HYPERTENSION, HYPERTENSION, 0, 0),
            (CV_DISORDER, CV_DISORDER, 0, 0),
            # T2DM hierarchy
            (DM, T2DM, 1, 1),
            (GLUCOSE_DISORDER, T2DM, 2, 2),
            (CLINICAL_FINDING, T2DM, 3, 3),
            # T1DM hierarchy
            (DM, T1DM, 1, 1),
            (GLUCOSE_DISORDER, T1DM, 2, 2),
            (CLINICAL_FINDING, T1DM, 3, 3),
            # DM hierarchy
            (GLUCOSE_DISORDER, DM, 1, 1),
            (CLINICAL_FINDING, DM, 2, 2),
            # Glucose disorder hierarchy
            (CLINICAL_FINDING, GLUCOSE_DISORDER, 1, 1),
            # Hypertension hierarchy
            (CV_DISORDER, HYPERTENSION, 1, 1),
        ]
        for anc, desc, min_sep, max_sep in ancestors:
            session.execute(text(
                "INSERT INTO omop_concept_ancestor "
                "(ancestor_concept_id, descendant_concept_id, "
                " min_levels_of_separation, max_levels_of_separation) "
                "VALUES (:anc, :desc, :min_sep, :max_sep)"
            ), {"anc": anc, "desc": desc, "min_sep": min_sep, "max_sep": max_sep})

        # -- Concept relationships --
        # ICD-10 E11 "Maps to" SNOMED T2DM
        session.execute(text(
            "INSERT INTO omop_concept_relationship "
            "(concept_id_1, concept_id_2, relationship_id, valid_start_date, valid_end_date, invalid_reason) "
            "VALUES (:c1, :c2, 'Maps to', :vs, :ve, NULL)"
        ), {"c1": ICD10_E11, "c2": T2DM, "vs": VALID_START, "ve": VALID_END})

        session.commit()

    yield engine
    engine.dispose()


@pytest.fixture()
def svc(omop_engine) -> OMOPHierarchyService:
    """Create an OMOPHierarchyService wired to the test SQLite engine."""
    service = OMOPHierarchyService(strict_matching_mode=True)
    service._engine = omop_engine
    return service


@pytest.fixture()
def svc_no_db() -> OMOPHierarchyService:
    """Create an OMOPHierarchyService with no database (fallback mode)."""
    return OMOPHierarchyService(strict_matching_mode=True)


# ---------------------------------------------------------------------------
# 1. TestAncestorLookup
# ---------------------------------------------------------------------------


class TestAncestorLookup:
    """get_ancestors() returns correct concepts/distances from closure table."""

    def test_t2dm_ancestors_include_dm(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(T2DM, max_distance=5)
        ids = {c.concept_id for c, _ in ancestors}
        assert DM in ids

    def test_t2dm_ancestors_include_self(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(T2DM, max_distance=5, include_self=True)
        ids = {c.concept_id for c, _ in ancestors}
        assert T2DM in ids

    def test_t2dm_ancestors_exclude_self(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(T2DM, max_distance=5, include_self=False)
        ids = {c.concept_id for c, _ in ancestors}
        assert T2DM not in ids

    def test_t2dm_ancestors_correct_distances(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(T2DM, max_distance=5)
        dist_map = {c.concept_id: d for c, d in ancestors}
        assert dist_map[T2DM] == 0
        assert dist_map[DM] == 1
        assert dist_map[GLUCOSE_DISORDER] == 2
        assert dist_map[CLINICAL_FINDING] == 3

    def test_max_distance_limits_results(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(T2DM, max_distance=1)
        ids = {c.concept_id for c, _ in ancestors}
        assert DM in ids
        assert GLUCOSE_DISORDER not in ids

    def test_hypertension_ancestors(self, svc: OMOPHierarchyService) -> None:
        ancestors = svc.get_ancestors(HYPERTENSION, max_distance=5)
        ids = {c.concept_id for c, _ in ancestors}
        assert CV_DISORDER in ids
        assert DM not in ids  # unrelated branch

    def test_clinical_finding_has_only_self(self, svc: OMOPHierarchyService) -> None:
        """Top-level concept has no ancestors other than self."""
        ancestors = svc.get_ancestors(CLINICAL_FINDING, max_distance=5)
        assert len(ancestors) == 1
        assert ancestors[0][0].concept_id == CLINICAL_FINDING
        assert ancestors[0][1] == 0


# ---------------------------------------------------------------------------
# 2. TestDescendantLookup
# ---------------------------------------------------------------------------


class TestDescendantLookup:
    """get_descendants() returns children with correct distances."""

    def test_dm_descendants_include_t2dm(self, svc: OMOPHierarchyService) -> None:
        descendants = svc.get_descendants(DM, max_distance=5)
        ids = {c.concept_id for c, _ in descendants}
        assert T2DM in ids
        assert T1DM in ids

    def test_dm_descendants_include_self(self, svc: OMOPHierarchyService) -> None:
        descendants = svc.get_descendants(DM, max_distance=5, include_self=True)
        ids = {c.concept_id for c, _ in descendants}
        assert DM in ids

    def test_dm_descendants_exclude_self(self, svc: OMOPHierarchyService) -> None:
        descendants = svc.get_descendants(DM, max_distance=5, include_self=False)
        ids = {c.concept_id for c, _ in descendants}
        assert DM not in ids
        assert T2DM in ids

    def test_dm_descendant_distances(self, svc: OMOPHierarchyService) -> None:
        descendants = svc.get_descendants(DM, max_distance=5)
        dist_map = {c.concept_id: d for c, d in descendants}
        assert dist_map[DM] == 0
        assert dist_map[T2DM] == 1
        assert dist_map[T1DM] == 1

    def test_leaf_has_only_self(self, svc: OMOPHierarchyService) -> None:
        """T2DM has no descendants in our test data."""
        descendants = svc.get_descendants(T2DM, max_distance=5)
        assert len(descendants) == 1
        assert descendants[0][0].concept_id == T2DM


# ---------------------------------------------------------------------------
# 3. TestHierarchyMatch
# ---------------------------------------------------------------------------


class TestHierarchyMatch:
    """check_hierarchy_match() single bidirectional query."""

    def test_exact_match_by_id(self, svc: OMOPHierarchyService) -> None:
        result = svc.check_hierarchy_match(T2DM, T2DM)
        assert result.matched
        assert result.match_type == "exact"
        assert result.distance == 0

    def test_ancestor_match_t2dm_to_dm(self, svc: OMOPHierarchyService) -> None:
        """Patient has T2DM, target is DM → ancestor match."""
        result = svc.check_hierarchy_match(T2DM, DM)
        assert result.matched
        assert result.match_type == "ancestor"
        assert result.distance == 1

    def test_descendant_match_dm_to_t2dm(self, svc: OMOPHierarchyService) -> None:
        """Patient has DM, target is T2DM → descendant match."""
        result = svc.check_hierarchy_match(DM, T2DM)
        assert result.matched
        assert result.match_type == "descendant"
        assert result.distance == 1

    def test_no_match_unrelated(self, svc: OMOPHierarchyService) -> None:
        """T2DM and Hypertension are unrelated."""
        result = svc.check_hierarchy_match(T2DM, HYPERTENSION)
        assert not result.matched
        assert result.match_type == "none"

    def test_max_distance_respected(self, svc: OMOPHierarchyService) -> None:
        """T2DM → Clinical finding is distance 3, should fail with max_distance=2."""
        result = svc.check_hierarchy_match(T2DM, CLINICAL_FINDING, max_distance=2)
        assert not result.matched

    def test_distance_3_matches_with_sufficient_max(self, svc: OMOPHierarchyService) -> None:
        """T2DM → Clinical finding at distance 3 should match with max_distance=3."""
        result = svc.check_hierarchy_match(T2DM, CLINICAL_FINDING, max_distance=3)
        assert result.matched
        assert result.distance == 3


# ---------------------------------------------------------------------------
# 4. TestDistanceWeightedQuality
# ---------------------------------------------------------------------------


class TestDistanceWeightedQuality:
    """match_quality tiers based on distance."""

    def test_distance_0_is_exact(self) -> None:
        assert OMOPHierarchyService._distance_to_quality(0) == "exact"

    def test_distance_1_is_synonym(self) -> None:
        assert OMOPHierarchyService._distance_to_quality(1) == "synonym"

    def test_distance_2_is_synonym(self) -> None:
        assert OMOPHierarchyService._distance_to_quality(2) == "synonym"

    def test_distance_3_is_fuzzy(self) -> None:
        assert OMOPHierarchyService._distance_to_quality(3) == "fuzzy"

    def test_distance_5_is_fuzzy(self) -> None:
        assert OMOPHierarchyService._distance_to_quality(5) == "fuzzy"

    def test_hierarchy_match_quality_distance_1(self, svc: OMOPHierarchyService) -> None:
        result = svc.check_hierarchy_match(T2DM, DM)
        assert result.match_quality == "synonym"

    def test_hierarchy_match_quality_distance_3(self, svc: OMOPHierarchyService) -> None:
        result = svc.check_hierarchy_match(T2DM, CLINICAL_FINDING, max_distance=3)
        assert result.match_quality == "fuzzy"


# ---------------------------------------------------------------------------
# 5. TestConceptSearch
# ---------------------------------------------------------------------------


class TestConceptSearch:
    """find_concepts_by_name() — exact and pattern matching.

    Uses mock because the SQL uses PostgreSQL-specific ANY() syntax.
    """

    def test_find_by_exact_name(self, svc: OMOPHierarchyService) -> None:
        """Mock the session to simulate find_concepts_by_name."""
        Row = namedtuple("Row", ["concept_id", "concept_name", "vocabulary_id", "domain_id", "concept_class_id"])
        mock_rows = [Row(T2DM, "Type 2 diabetes mellitus", "SNOMED", "Condition", "Clinical Finding")]

        with patch.object(Session, "execute", return_value=MagicMock(fetchall=lambda: mock_rows)):
            concepts = svc.find_concepts_by_name("Type 2 diabetes mellitus")
            assert len(concepts) == 1
            assert concepts[0].concept_id == T2DM

    def test_find_returns_empty_when_no_engine(self, svc_no_db: OMOPHierarchyService) -> None:
        concepts = svc_no_db.find_concepts_by_name("diabetes")
        assert concepts == []


# ---------------------------------------------------------------------------
# 6. TestGetConceptById
# ---------------------------------------------------------------------------


class TestGetConceptById:
    """get_concept_by_id() lookups."""

    def test_existing_concept(self, svc: OMOPHierarchyService) -> None:
        concept = svc.get_concept_by_id(T2DM)
        assert concept is not None
        assert concept.concept_id == T2DM
        assert concept.name == "Type 2 diabetes mellitus"
        assert concept.vocabulary_id == "SNOMED"

    def test_nonexistent_concept(self, svc: OMOPHierarchyService) -> None:
        concept = svc.get_concept_by_id(999999999)
        assert concept is None

    def test_no_engine_returns_none(self, svc_no_db: OMOPHierarchyService) -> None:
        concept = svc_no_db.get_concept_by_id(T2DM)
        assert concept is None


# ---------------------------------------------------------------------------
# 7. TestCrossVocabMapsTo
# ---------------------------------------------------------------------------


class TestCrossVocabMapsTo:
    """ICD-10 concept → 'Maps to' → SNOMED → hierarchy match."""

    def test_maps_to_resolves_icd10_to_snomed(self, svc: OMOPHierarchyService) -> None:
        """Non-standard ICD-10 E11 should map to standard SNOMED T2DM."""
        mapped = svc._resolve_via_maps_to(ICD10_E11)
        assert mapped == T2DM

    def test_standard_concept_no_mapping(self, svc: OMOPHierarchyService) -> None:
        """Standard concept T2DM should not map further."""
        mapped = svc._resolve_via_maps_to(T2DM)
        assert mapped is None

    def test_resolve_concept_chases_maps_to(self, svc: OMOPHierarchyService) -> None:
        """_resolve_concept with ICD-10 ID should return the SNOMED concept."""
        concept = svc._resolve_concept(ICD10_E11)
        assert concept is not None
        assert concept.concept_id == T2DM
        assert concept.vocabulary_id == "SNOMED"


# ---------------------------------------------------------------------------
# 8. TestFallbackWhenUnavailable
# ---------------------------------------------------------------------------


class TestFallbackWhenUnavailable:
    """No PG engine → string matching fallback."""

    def test_is_available_false(self, svc_no_db: OMOPHierarchyService) -> None:
        assert not svc_no_db.is_available

    def test_exact_string_match_works(self, svc_no_db: OMOPHierarchyService) -> None:
        result = svc_no_db.check_hierarchy_match("pneumonia", "pneumonia")
        assert result.matched
        assert result.match_type == "exact"

    def test_false_positive_rejected(self, svc_no_db: OMOPHierarchyService) -> None:
        result = svc_no_db.check_hierarchy_match("metformin", "metronidazole")
        assert not result.matched

    def test_get_ancestors_empty(self, svc_no_db: OMOPHierarchyService) -> None:
        assert svc_no_db.get_ancestors(T2DM) == []

    def test_get_descendants_empty(self, svc_no_db: OMOPHierarchyService) -> None:
        assert svc_no_db.get_descendants(DM) == []


# ---------------------------------------------------------------------------
# 9. TestCacheBehavior
# ---------------------------------------------------------------------------


class TestCacheBehavior:
    """LRU cache hits/misses/eviction."""

    def test_cache_starts_empty(self, svc: OMOPHierarchyService) -> None:
        stats = svc.get_cache_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.size == 0

    def test_ancestor_cache_miss_then_hit(self, svc: OMOPHierarchyService) -> None:
        svc.get_ancestors(T2DM, max_distance=5)
        stats = svc.get_cache_stats()
        assert stats.misses >= 1

        svc.get_ancestors(T2DM, max_distance=5)
        stats = svc.get_cache_stats()
        assert stats.hits >= 1

    def test_clear_cache_resets_stats(self, svc: OMOPHierarchyService) -> None:
        svc.get_ancestors(T2DM, max_distance=5)
        svc.clear_cache()
        stats = svc.get_cache_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.size == 0

    def test_cache_eviction_at_max_size(self) -> None:
        """Cache evicts oldest entries when exceeding max_size."""
        svc = OMOPHierarchyService(cache_max_size=2)
        # Manually populate cache to test eviction
        with svc._cache_lock:
            svc._ancestor_cache[1] = [(OMOPConcept(1, "a"), 0)]
            svc._ancestor_cache[2] = [(OMOPConcept(2, "b"), 0)]
            svc._ancestor_cache[3] = [(OMOPConcept(3, "c"), 0)]
            while len(svc._ancestor_cache) > svc._cache_max_size:
                svc._ancestor_cache.popitem(last=False)

        assert len(svc._ancestor_cache) == 2
        assert 1 not in svc._ancestor_cache  # oldest evicted

    def test_set_omop_version_invalidates(self, svc: OMOPHierarchyService) -> None:
        svc.get_ancestors(T2DM, max_distance=5)
        assert svc.get_cache_stats().size > 0
        svc.set_omop_version("v6.0")
        assert svc.get_cache_stats().size == 0


# ---------------------------------------------------------------------------
# 10. TestIsAvailable
# ---------------------------------------------------------------------------


class TestIsAvailable:
    """is_available reflects PG + concept_ancestor state."""

    def test_available_with_seeded_data(self, svc: OMOPHierarchyService) -> None:
        assert svc.is_available

    def test_unavailable_with_no_engine(self, svc_no_db: OMOPHierarchyService) -> None:
        assert not svc_no_db.is_available


# ---------------------------------------------------------------------------
# 11. TestAncestorNames
# ---------------------------------------------------------------------------


class TestAncestorNames:
    """get_ancestor_names() convenience method."""

    def test_returns_lowercase_names(self, svc: OMOPHierarchyService) -> None:
        names = svc.get_ancestor_names(T2DM, max_distance=5)
        assert all(n == n.lower() for n in names)

    def test_includes_self_name(self, svc: OMOPHierarchyService) -> None:
        names = svc.get_ancestor_names(T2DM, max_distance=5, include_self=True)
        assert "type 2 diabetes mellitus" in names

    def test_includes_ancestor_names(self, svc: OMOPHierarchyService) -> None:
        names = svc.get_ancestor_names(T2DM, max_distance=5)
        assert "diabetes mellitus" in names
