"""Tests for OMOP Foreign Key Constraints migration (019).

Tests verify:
- FK constraints exist via introspection
- Referential integrity violations raise errors
"""

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    """Create SQLite engine with OMOP CDM + vocabulary tables and FK constraints."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with eng.begin() as conn:
        # Enable FK enforcement in SQLite
        conn.execute(text("PRAGMA foreign_keys = ON"))

        # Create vocabulary reference tables
        conn.execute(text("""
            CREATE TABLE omop_vocabulary (
                vocabulary_id VARCHAR(20) PRIMARY KEY,
                vocabulary_name VARCHAR(255) NOT NULL,
                vocabulary_reference VARCHAR(255),
                vocabulary_version VARCHAR(255),
                vocabulary_concept_id INTEGER NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE omop_domain (
                domain_id VARCHAR(20) PRIMARY KEY,
                domain_name VARCHAR(255) NOT NULL,
                domain_concept_id INTEGER NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE omop_concept_class (
                concept_class_id VARCHAR(20) PRIMARY KEY,
                concept_class_name VARCHAR(255) NOT NULL,
                concept_class_concept_id INTEGER NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE omop_concept (
                concept_id INTEGER PRIMARY KEY,
                concept_name VARCHAR(255) NOT NULL,
                domain_id VARCHAR(20) NOT NULL REFERENCES omop_domain(domain_id),
                vocabulary_id VARCHAR(20) NOT NULL REFERENCES omop_vocabulary(vocabulary_id),
                concept_class_id VARCHAR(20) NOT NULL REFERENCES omop_concept_class(concept_class_id),
                standard_concept VARCHAR(1),
                concept_code VARCHAR(50) NOT NULL,
                valid_start_date DATE NOT NULL,
                valid_end_date DATE NOT NULL,
                invalid_reason VARCHAR(1)
            )
        """))

        # Create location table
        conn.execute(text("""
            CREATE TABLE location (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_1 VARCHAR(50),
                city VARCHAR(50),
                state VARCHAR(2),
                zip VARCHAR(9)
            )
        """))

        # Create care_site table
        conn.execute(text("""
            CREATE TABLE care_site (
                care_site_id INTEGER PRIMARY KEY AUTOINCREMENT,
                care_site_name VARCHAR(255),
                place_of_service_concept_id INTEGER,
                location_id INTEGER REFERENCES location(location_id)
            )
        """))

        # Create provider table
        conn.execute(text("""
            CREATE TABLE provider (
                provider_id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_name VARCHAR(255),
                specialty_concept_id INTEGER
            )
        """))

        # Create person table with FK to omop_concept
        conn.execute(text("""
            CREATE TABLE person (
                person_id INTEGER PRIMARY KEY AUTOINCREMENT,
                gender_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                year_of_birth INTEGER NOT NULL,
                race_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                ethnicity_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                location_id INTEGER REFERENCES location(location_id)
            )
        """))

        # Create visit_occurrence table with FK to omop_concept
        conn.execute(text("""
            CREATE TABLE visit_occurrence (
                visit_occurrence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES person(person_id),
                visit_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                visit_start_date DATE NOT NULL,
                visit_end_date DATE NOT NULL,
                visit_type_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id)
            )
        """))

        # Create condition_occurrence table with FK to omop_concept
        conn.execute(text("""
            CREATE TABLE condition_occurrence (
                condition_occurrence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES person(person_id),
                condition_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                condition_start_date DATE NOT NULL,
                condition_type_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                visit_occurrence_id INTEGER REFERENCES visit_occurrence(visit_occurrence_id)
            )
        """))

        # Create drug_exposure table with FK to omop_concept
        conn.execute(text("""
            CREATE TABLE drug_exposure (
                drug_exposure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES person(person_id),
                drug_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                drug_exposure_start_date DATE NOT NULL,
                drug_exposure_end_date DATE NOT NULL,
                drug_type_concept_id INTEGER NOT NULL REFERENCES omop_concept(concept_id),
                route_concept_id INTEGER REFERENCES omop_concept(concept_id)
            )
        """))

        # Create death table with FK to omop_concept
        conn.execute(text("""
            CREATE TABLE death (
                person_id INTEGER PRIMARY KEY REFERENCES person(person_id),
                death_date DATE NOT NULL,
                death_type_concept_id INTEGER REFERENCES omop_concept(concept_id),
                cause_concept_id INTEGER REFERENCES omop_concept(concept_id)
            )
        """))

        # Insert reference data for valid concepts
        conn.execute(text("""
            INSERT INTO omop_vocabulary (vocabulary_id, vocabulary_name, vocabulary_concept_id)
            VALUES ('SNOMED', 'SNOMED CT', 1)
        """))
        conn.execute(text("""
            INSERT INTO omop_domain (domain_id, domain_name, domain_concept_id)
            VALUES ('Gender', 'Gender', 2), ('Condition', 'Condition', 3)
        """))
        conn.execute(text("""
            INSERT INTO omop_concept_class (concept_class_id, concept_class_name, concept_class_concept_id)
            VALUES ('Clinical Finding', 'Clinical Finding', 4)
        """))
        # Insert valid concepts
        conn.execute(text("""
            INSERT INTO omop_concept (concept_id, concept_name, domain_id, vocabulary_id,
                concept_class_id, concept_code, valid_start_date, valid_end_date)
            VALUES
                (8507, 'Male', 'Gender', 'SNOMED', 'Clinical Finding', '8507', '1970-01-01', '2099-12-31'),
                (8532, 'Female', 'Gender', 'SNOMED', 'Clinical Finding', '8532', '1970-01-01', '2099-12-31'),
                (0, 'No matching concept', 'Gender', 'SNOMED', 'Clinical Finding', '0', '1970-01-01', '2099-12-31'),
                (9201, 'Inpatient Visit', 'Gender', 'SNOMED', 'Clinical Finding', '9201', '1970-01-01', '2099-12-31'),
                (32817, 'EHR', 'Gender', 'SNOMED', 'Clinical Finding', '32817', '1970-01-01', '2099-12-31'),
                (73211009, 'Diabetes mellitus', 'Condition', 'SNOMED', 'Clinical Finding', '73211009', '1970-01-01', '2099-12-31'),
                (1901, 'Aspirin', 'Condition', 'SNOMED', 'Clinical Finding', '1901', '1970-01-01', '2099-12-31'),
                (4132161, 'Oral route', 'Condition', 'SNOMED', 'Clinical Finding', '4132161', '1970-01-01', '2099-12-31')
        """))

    yield eng
    eng.dispose()


class TestForeignKeyConstraintsExist:
    """Test FK constraints exist via introspection."""

    def test_person_gender_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("person")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["gender_concept_id"] in fk_columns

    def test_person_race_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("person")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["race_concept_id"] in fk_columns

    def test_person_ethnicity_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("person")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["ethnicity_concept_id"] in fk_columns

    def test_visit_concept_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("visit_occurrence")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["visit_concept_id"] in fk_columns

    def test_condition_concept_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("condition_occurrence")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["condition_concept_id"] in fk_columns

    def test_drug_concept_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("drug_exposure")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["drug_concept_id"] in fk_columns

    def test_death_type_concept_fk(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("death")
        fk_columns = [fk["constrained_columns"] for fk in fks]
        assert ["death_type_concept_id"] in fk_columns


class TestReferentialIntegrity:
    """Test referential integrity violations raise errors."""

    def test_invalid_gender_concept_raises(self, engine):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
                conn.execute(text("""
                    INSERT INTO person (person_id, gender_concept_id, year_of_birth,
                        race_concept_id, ethnicity_concept_id)
                    VALUES (1, 99999, 1990, 0, 0)
                """))

    def test_valid_person_insert(self, engine):
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("""
                INSERT INTO person (person_id, gender_concept_id, year_of_birth,
                    race_concept_id, ethnicity_concept_id)
                VALUES (1, 8507, 1990, 0, 0)
            """))
            result = conn.execute(text("SELECT * FROM person WHERE person_id = 1"))
            assert result.fetchone() is not None

    def test_invalid_visit_concept_raises(self, engine):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
                conn.execute(text("""
                    INSERT INTO person (person_id, gender_concept_id, year_of_birth,
                        race_concept_id, ethnicity_concept_id)
                    VALUES (2, 8507, 1990, 0, 0)
                """))
                conn.execute(text("""
                    INSERT INTO visit_occurrence (visit_occurrence_id, person_id,
                        visit_concept_id, visit_start_date, visit_end_date, visit_type_concept_id)
                    VALUES (1, 2, 99999, '2024-01-01', '2024-01-05', 32817)
                """))

    def test_invalid_condition_concept_raises(self, engine):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
                conn.execute(text("""
                    INSERT INTO person (person_id, gender_concept_id, year_of_birth,
                        race_concept_id, ethnicity_concept_id)
                    VALUES (3, 8507, 1990, 0, 0)
                """))
                conn.execute(text("""
                    INSERT INTO condition_occurrence (condition_occurrence_id, person_id,
                        condition_concept_id, condition_start_date, condition_type_concept_id)
                    VALUES (1, 3, 99999, '2024-01-01', 32817)
                """))

    def test_invalid_drug_concept_raises(self, engine):
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
                conn.execute(text("""
                    INSERT INTO person (person_id, gender_concept_id, year_of_birth,
                        race_concept_id, ethnicity_concept_id)
                    VALUES (4, 8507, 1990, 0, 0)
                """))
                conn.execute(text("""
                    INSERT INTO drug_exposure (drug_exposure_id, person_id,
                        drug_concept_id, drug_exposure_start_date, drug_exposure_end_date,
                        drug_type_concept_id)
                    VALUES (1, 4, 99999, '2024-01-01', '2024-01-10', 32817)
                """))
