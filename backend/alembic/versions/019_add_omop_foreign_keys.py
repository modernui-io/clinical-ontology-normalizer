"""Add foreign key constraints between OMOP CDM clinical tables and vocabulary tables.

Revision ID: 019
Revises: 018
Create Date: 2026-01-24

This migration adds FK constraints from concept_id columns in clinical tables
to the omop_concept reference table, enforcing referential integrity between
clinical data and standardized vocabulary.

Constraints Added:
    person: gender_concept_id, race_concept_id, ethnicity_concept_id
    visit_occurrence: visit_concept_id, visit_type_concept_id
    condition_occurrence: condition_concept_id, condition_type_concept_id
    drug_exposure: drug_concept_id, drug_type_concept_id, route_concept_id
    procedure_occurrence: procedure_concept_id, procedure_type_concept_id
    measurement: measurement_concept_id, measurement_type_concept_id, unit_concept_id
    observation: observation_concept_id, observation_type_concept_id
    death: death_type_concept_id, cause_concept_id
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define all FK constraints: (table, column, constraint_name)
FK_CONSTRAINTS = [
    # Person table
    ("person", "gender_concept_id", "fk_person_gender_concept"),
    ("person", "race_concept_id", "fk_person_race_concept"),
    ("person", "ethnicity_concept_id", "fk_person_ethnicity_concept"),
    # Visit occurrence
    ("visit_occurrence", "visit_concept_id", "fk_visit_concept"),
    ("visit_occurrence", "visit_type_concept_id", "fk_visit_type_concept"),
    # Condition occurrence
    ("condition_occurrence", "condition_concept_id", "fk_condition_concept"),
    ("condition_occurrence", "condition_type_concept_id", "fk_condition_type_concept"),
    # Drug exposure
    ("drug_exposure", "drug_concept_id", "fk_drug_concept"),
    ("drug_exposure", "drug_type_concept_id", "fk_drug_type_concept"),
    ("drug_exposure", "route_concept_id", "fk_drug_route_concept"),
    # Procedure occurrence
    ("procedure_occurrence", "procedure_concept_id", "fk_procedure_concept"),
    ("procedure_occurrence", "procedure_type_concept_id", "fk_procedure_type_concept"),
    # Measurement
    ("measurement", "measurement_concept_id", "fk_measurement_concept"),
    ("measurement", "measurement_type_concept_id", "fk_measurement_type_concept"),
    ("measurement", "unit_concept_id", "fk_measurement_unit_concept"),
    # Observation
    ("observation", "observation_concept_id", "fk_observation_concept"),
    ("observation", "observation_type_concept_id", "fk_observation_type_concept"),
    # Death
    ("death", "death_type_concept_id", "fk_death_type_concept"),
    ("death", "cause_concept_id", "fk_death_cause_concept"),
]


def upgrade() -> None:
    for table, column, constraint_name in FK_CONSTRAINTS:
        op.create_foreign_key(
            constraint_name,
            table,
            "omop_concept",
            [column],
            ["concept_id"],
        )


def downgrade() -> None:
    for table, column, constraint_name in reversed(FK_CONSTRAINTS):
        op.drop_constraint(constraint_name, table, type_="foreignkey")
