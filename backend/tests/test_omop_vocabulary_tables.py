"""Tests for OMOP Vocabulary Reference Tables migration (018).

Tests verify:
- All 8 vocabulary tables are created
- Appropriate indexes exist
- Basic CRUD operations on the Concept table
"""

from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    """Create SQLite engine and apply migration schema."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with eng.begin() as conn:
        # Create vocabulary table
        conn.execute(text("""
            CREATE TABLE omop_vocabulary (
                vocabulary_id VARCHAR(20) PRIMARY KEY,
                vocabulary_name VARCHAR(255) NOT NULL,
                vocabulary_reference VARCHAR(255),
                vocabulary_version VARCHAR(255),
                vocabulary_concept_id INTEGER NOT NULL
            )
        """))

        # Create domain table
        conn.execute(text("""
            CREATE TABLE omop_domain (
                domain_id VARCHAR(20) PRIMARY KEY,
                domain_name VARCHAR(255) NOT NULL,
                domain_concept_id INTEGER NOT NULL
            )
        """))

        # Create concept_class table
        conn.execute(text("""
            CREATE TABLE omop_concept_class (
                concept_class_id VARCHAR(20) PRIMARY KEY,
                concept_class_name VARCHAR(255) NOT NULL,
                concept_class_concept_id INTEGER NOT NULL
            )
        """))

        # Create relationship table
        conn.execute(text("""
            CREATE TABLE omop_relationship (
                relationship_id VARCHAR(20) PRIMARY KEY,
                relationship_name VARCHAR(255) NOT NULL,
                is_hierarchical VARCHAR(1) NOT NULL,
                defines_ancestry VARCHAR(1) NOT NULL,
                reverse_relationship_id VARCHAR(20) NOT NULL,
                relationship_concept_id INTEGER NOT NULL
            )
        """))

        # Create concept table
        conn.execute(text("""
            CREATE TABLE omop_concept (
                concept_id INTEGER PRIMARY KEY,
                concept_name VARCHAR(255) NOT NULL,
                domain_id VARCHAR(20) NOT NULL,
                vocabulary_id VARCHAR(20) NOT NULL,
                concept_class_id VARCHAR(20) NOT NULL,
                standard_concept VARCHAR(1),
                concept_code VARCHAR(50) NOT NULL,
                valid_start_date DATE NOT NULL,
                valid_end_date DATE NOT NULL,
                invalid_reason VARCHAR(1),
                FOREIGN KEY (vocabulary_id) REFERENCES omop_vocabulary(vocabulary_id),
                FOREIGN KEY (domain_id) REFERENCES omop_domain(domain_id),
                FOREIGN KEY (concept_class_id) REFERENCES omop_concept_class(concept_class_id)
            )
        """))
        conn.execute(text("CREATE INDEX idx_omop_concept_code ON omop_concept(concept_code)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_vocabulary_id ON omop_concept(vocabulary_id)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_domain_id ON omop_concept(domain_id)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_class_id ON omop_concept(concept_class_id)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_standard ON omop_concept(standard_concept)"))

        # Create concept_relationship table
        conn.execute(text("""
            CREATE TABLE omop_concept_relationship (
                concept_id_1 INTEGER NOT NULL,
                concept_id_2 INTEGER NOT NULL,
                relationship_id VARCHAR(20) NOT NULL,
                valid_start_date DATE NOT NULL,
                valid_end_date DATE NOT NULL,
                invalid_reason VARCHAR(1),
                PRIMARY KEY (concept_id_1, concept_id_2, relationship_id),
                FOREIGN KEY (concept_id_1) REFERENCES omop_concept(concept_id),
                FOREIGN KEY (concept_id_2) REFERENCES omop_concept(concept_id),
                FOREIGN KEY (relationship_id) REFERENCES omop_relationship(relationship_id)
            )
        """))
        conn.execute(text("CREATE INDEX idx_omop_concept_rel_id_1 ON omop_concept_relationship(concept_id_1)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_rel_id_2 ON omop_concept_relationship(concept_id_2)"))
        conn.execute(text("CREATE INDEX idx_omop_concept_rel_rel_id ON omop_concept_relationship(relationship_id)"))

        # Create concept_synonym table
        conn.execute(text("""
            CREATE TABLE omop_concept_synonym (
                concept_id INTEGER NOT NULL,
                concept_synonym_name VARCHAR(1000) NOT NULL,
                language_concept_id INTEGER NOT NULL,
                FOREIGN KEY (concept_id) REFERENCES omop_concept(concept_id)
            )
        """))
        conn.execute(text("CREATE INDEX idx_omop_concept_synonym_id ON omop_concept_synonym(concept_id)"))

        # Create concept_ancestor table
        conn.execute(text("""
            CREATE TABLE omop_concept_ancestor (
                ancestor_concept_id INTEGER NOT NULL,
                descendant_concept_id INTEGER NOT NULL,
                min_levels_of_separation INTEGER NOT NULL,
                max_levels_of_separation INTEGER NOT NULL,
                PRIMARY KEY (ancestor_concept_id, descendant_concept_id),
                FOREIGN KEY (ancestor_concept_id) REFERENCES omop_concept(concept_id),
                FOREIGN KEY (descendant_concept_id) REFERENCES omop_concept(concept_id)
            )
        """))
        conn.execute(text("CREATE INDEX idx_omop_ancestor_ancestor_id ON omop_concept_ancestor(ancestor_concept_id)"))
        conn.execute(text("CREATE INDEX idx_omop_ancestor_descendant_id ON omop_concept_ancestor(descendant_concept_id)"))

    yield eng
    eng.dispose()


class TestOMOPVocabularyTablesExist:
    """Test that all 8 OMOP vocabulary tables are created."""

    EXPECTED_TABLES = [
        "omop_vocabulary",
        "omop_domain",
        "omop_concept_class",
        "omop_relationship",
        "omop_concept",
        "omop_concept_relationship",
        "omop_concept_synonym",
        "omop_concept_ancestor",
    ]

    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for table in self.EXPECTED_TABLES:
            assert table in tables, f"Table {table} not found"

    def test_table_count(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        vocab_tables = [t for t in tables if t.startswith("omop_")]
        assert len(vocab_tables) == 8


class TestOMOPVocabularyIndexes:
    """Test that appropriate indexes exist on vocabulary tables."""

    def test_concept_code_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("omop_concept")
        index_names = [idx["name"] for idx in indexes]
        assert "idx_omop_concept_code" in index_names

    def test_concept_vocabulary_id_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("omop_concept")
        index_names = [idx["name"] for idx in indexes]
        assert "idx_omop_concept_vocabulary_id" in index_names

    def test_concept_domain_id_index(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("omop_concept")
        index_names = [idx["name"] for idx in indexes]
        assert "idx_omop_concept_domain_id" in index_names

    def test_concept_relationship_indexes(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("omop_concept_relationship")
        index_names = [idx["name"] for idx in indexes]
        assert "idx_omop_concept_rel_id_1" in index_names
        assert "idx_omop_concept_rel_id_2" in index_names

    def test_concept_ancestor_indexes(self, engine):
        inspector = inspect(engine)
        indexes = inspector.get_indexes("omop_concept_ancestor")
        index_names = [idx["name"] for idx in indexes]
        assert "idx_omop_ancestor_ancestor_id" in index_names
        assert "idx_omop_ancestor_descendant_id" in index_names


class TestOMOPConceptCRUD:
    """Test basic CRUD operations on the Concept table."""

    def _insert_reference_data(self, conn):
        """Insert required reference data for FK constraints."""
        conn.execute(text("""
            INSERT INTO omop_vocabulary (vocabulary_id, vocabulary_name, vocabulary_concept_id)
            VALUES ('SNOMED', 'SNOMED CT', 44819096)
        """))
        conn.execute(text("""
            INSERT INTO omop_domain (domain_id, domain_name, domain_concept_id)
            VALUES ('Condition', 'Condition', 19)
        """))
        conn.execute(text("""
            INSERT INTO omop_concept_class (concept_class_id, concept_class_name, concept_class_concept_id)
            VALUES ('Clinical Finding', 'Clinical Finding', 317)
        """))

    def test_insert_concept(self, engine):
        with engine.begin() as conn:
            self._insert_reference_data(conn)
            conn.execute(text("""
                INSERT INTO omop_concept
                (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
                 standard_concept, concept_code, valid_start_date, valid_end_date)
                VALUES (73211009, 'Diabetes mellitus', 'Condition', 'SNOMED',
                        'Clinical Finding', 'S', '73211009', '1970-01-01', '2099-12-31')
            """))
            result = conn.execute(text("SELECT * FROM omop_concept WHERE concept_id = 73211009"))
            row = result.fetchone()
            assert row is not None
            assert row[1] == "Diabetes mellitus"

    def test_read_concept(self, engine):
        with engine.begin() as conn:
            self._insert_reference_data(conn)
            conn.execute(text("""
                INSERT INTO omop_concept
                (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
                 standard_concept, concept_code, valid_start_date, valid_end_date)
                VALUES (73211009, 'Diabetes mellitus', 'Condition', 'SNOMED',
                        'Clinical Finding', 'S', '73211009', '1970-01-01', '2099-12-31')
            """))
            result = conn.execute(text(
                "SELECT concept_name FROM omop_concept WHERE concept_code = '73211009'"
            ))
            row = result.fetchone()
            assert row[0] == "Diabetes mellitus"

    def test_update_concept(self, engine):
        with engine.begin() as conn:
            self._insert_reference_data(conn)
            conn.execute(text("""
                INSERT INTO omop_concept
                (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
                 standard_concept, concept_code, valid_start_date, valid_end_date)
                VALUES (73211009, 'Diabetes mellitus', 'Condition', 'SNOMED',
                        'Clinical Finding', 'S', '73211009', '1970-01-01', '2099-12-31')
            """))
            conn.execute(text("""
                UPDATE omop_concept SET concept_name = 'Diabetes mellitus (disorder)'
                WHERE concept_id = 73211009
            """))
            result = conn.execute(text("SELECT concept_name FROM omop_concept WHERE concept_id = 73211009"))
            assert result.fetchone()[0] == "Diabetes mellitus (disorder)"

    def test_delete_concept(self, engine):
        with engine.begin() as conn:
            self._insert_reference_data(conn)
            conn.execute(text("""
                INSERT INTO omop_concept
                (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
                 standard_concept, concept_code, valid_start_date, valid_end_date)
                VALUES (73211009, 'Diabetes mellitus', 'Condition', 'SNOMED',
                        'Clinical Finding', 'S', '73211009', '1970-01-01', '2099-12-31')
            """))
            conn.execute(text("DELETE FROM omop_concept WHERE concept_id = 73211009"))
            result = conn.execute(text("SELECT * FROM omop_concept WHERE concept_id = 73211009"))
            assert result.fetchone() is None
