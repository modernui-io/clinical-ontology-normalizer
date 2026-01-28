"""Create OMOP CDM v5.4 tables.

Revision ID: 017
Revises: 016
Create Date: 2026-01-19

This migration creates the OHDSI OMOP Common Data Model v5.4 tables.
The OMOP CDM provides a standardized format for observational health data.

Reference: https://ohdsi.github.io/CommonDataModel/cdm54.html

Tables Created (24 total):
    Health System Data:
        - location: Geographic locations
        - care_site: Healthcare facilities
        - provider: Healthcare providers

    Clinical Data:
        - person: Patient demographics
        - death: Death information
        - observation_period: Time periods with data
        - visit_occurrence: Healthcare encounters
        - visit_detail: Detailed encounter information
        - condition_occurrence: Diagnoses/conditions
        - drug_exposure: Medication administrations
        - procedure_occurrence: Clinical procedures
        - device_exposure: Device usage
        - measurement: Lab results and vitals
        - observation: Clinical observations
        - note: Clinical notes
        - note_nlp: NLP-extracted entities
        - specimen: Biological specimens

    Health Economics:
        - payer_plan_period: Insurance coverage
        - cost: Healthcare costs

    Derived Elements:
        - drug_era: Drug exposure periods
        - dose_era: Dose-specific periods
        - condition_era: Condition periods

    Metadata:
        - cdm_source: CDM source database metadata
        - metadata: General metadata storage
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: str | None = "016b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==========================================================================
    # Health System Data Tables
    # ==========================================================================

    # Create location table
    op.create_table(
        "location",
        sa.Column("location_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("address_1", sa.String(50), nullable=True),
        sa.Column("address_2", sa.String(50), nullable=True),
        sa.Column("city", sa.String(50), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(9), nullable=True),
        sa.Column("county", sa.String(20), nullable=True),
        sa.Column("location_source_value", sa.String(50), nullable=True),
        sa.Column("country_concept_id", sa.Integer(), nullable=True),
        sa.Column("country_source_value", sa.String(80), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
    )
    op.create_index("idx_location_zip", "location", ["zip"])

    # Create care_site table
    op.create_table(
        "care_site",
        sa.Column("care_site_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("care_site_name", sa.String(255), nullable=True),
        sa.Column("place_of_service_concept_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("location.location_id"), nullable=True),
        sa.Column("care_site_source_value", sa.String(50), nullable=True),
        sa.Column("place_of_service_source_value", sa.String(50), nullable=True),
    )

    # Create provider table
    op.create_table(
        "provider",
        sa.Column("provider_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider_name", sa.String(255), nullable=True),
        sa.Column("npi", sa.String(20), nullable=True),
        sa.Column("dea", sa.String(20), nullable=True),
        sa.Column("specialty_concept_id", sa.Integer(), nullable=True),
        sa.Column("care_site_id", sa.BigInteger(), sa.ForeignKey("care_site.care_site_id"), nullable=True),
        sa.Column("year_of_birth", sa.Integer(), nullable=True),
        sa.Column("gender_concept_id", sa.Integer(), nullable=True),
        sa.Column("provider_source_value", sa.String(50), nullable=True),
        sa.Column("specialty_source_value", sa.String(50), nullable=True),
        sa.Column("specialty_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("gender_source_value", sa.String(50), nullable=True),
        sa.Column("gender_source_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_provider_specialty", "provider", ["specialty_concept_id"])

    # ==========================================================================
    # Clinical Data Tables
    # ==========================================================================

    # Create person table
    op.create_table(
        "person",
        sa.Column("person_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("gender_concept_id", sa.Integer(), nullable=False),
        sa.Column("year_of_birth", sa.Integer(), nullable=False),
        sa.Column("month_of_birth", sa.Integer(), nullable=True),
        sa.Column("day_of_birth", sa.Integer(), nullable=True),
        sa.Column("birth_datetime", sa.DateTime(), nullable=True),
        sa.Column("race_concept_id", sa.Integer(), nullable=False),
        sa.Column("ethnicity_concept_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), sa.ForeignKey("location.location_id"), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("care_site_id", sa.BigInteger(), sa.ForeignKey("care_site.care_site_id"), nullable=True),
        sa.Column("person_source_value", sa.String(50), nullable=True),
        sa.Column("gender_source_value", sa.String(50), nullable=True),
        sa.Column("gender_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("race_source_value", sa.String(50), nullable=True),
        sa.Column("race_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("ethnicity_source_value", sa.String(50), nullable=True),
        sa.Column("ethnicity_source_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_person_gender", "person", ["gender_concept_id"])
    op.create_index("idx_person_race", "person", ["race_concept_id"])
    op.create_index("idx_person_ethnicity", "person", ["ethnicity_concept_id"])
    op.create_index("idx_person_location", "person", ["location_id"])

    # Create death table
    op.create_table(
        "death",
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), primary_key=True),
        sa.Column("death_date", sa.Date(), nullable=False),
        sa.Column("death_datetime", sa.DateTime(), nullable=True),
        sa.Column("death_type_concept_id", sa.Integer(), nullable=True),
        sa.Column("cause_concept_id", sa.Integer(), nullable=True),
        sa.Column("cause_source_value", sa.String(50), nullable=True),
        sa.Column("cause_source_concept_id", sa.Integer(), nullable=True),
    )

    # Create observation_period table
    op.create_table(
        "observation_period",
        sa.Column("observation_period_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("observation_period_start_date", sa.Date(), nullable=False),
        sa.Column("observation_period_end_date", sa.Date(), nullable=False),
        sa.Column("period_type_concept_id", sa.Integer(), nullable=False),
    )
    op.create_index("idx_observation_period_person", "observation_period", ["person_id"])

    # Create visit_occurrence table
    op.create_table(
        "visit_occurrence",
        sa.Column("visit_occurrence_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("visit_concept_id", sa.Integer(), nullable=False),
        sa.Column("visit_start_date", sa.Date(), nullable=False),
        sa.Column("visit_start_datetime", sa.DateTime(), nullable=True),
        sa.Column("visit_end_date", sa.Date(), nullable=False),
        sa.Column("visit_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("visit_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("care_site_id", sa.BigInteger(), sa.ForeignKey("care_site.care_site_id"), nullable=True),
        sa.Column("visit_source_value", sa.String(50), nullable=True),
        sa.Column("visit_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("admitted_from_concept_id", sa.Integer(), nullable=True),
        sa.Column("admitted_from_source_value", sa.String(50), nullable=True),
        sa.Column("discharged_to_concept_id", sa.Integer(), nullable=True),
        sa.Column("discharged_to_source_value", sa.String(50), nullable=True),
        sa.Column("preceding_visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
    )
    op.create_index("idx_visit_person_date", "visit_occurrence", ["person_id", "visit_start_date"])
    op.create_index("idx_visit_concept", "visit_occurrence", ["visit_concept_id"])

    # Create visit_detail table
    op.create_table(
        "visit_detail",
        sa.Column("visit_detail_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("visit_detail_concept_id", sa.Integer(), nullable=False),
        sa.Column("visit_detail_start_date", sa.Date(), nullable=False),
        sa.Column("visit_detail_start_datetime", sa.DateTime(), nullable=True),
        sa.Column("visit_detail_end_date", sa.Date(), nullable=False),
        sa.Column("visit_detail_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("visit_detail_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("care_site_id", sa.BigInteger(), sa.ForeignKey("care_site.care_site_id"), nullable=True),
        sa.Column("visit_detail_source_value", sa.String(50), nullable=True),
        sa.Column("visit_detail_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("admitted_from_concept_id", sa.Integer(), nullable=True),
        sa.Column("admitted_from_source_value", sa.String(50), nullable=True),
        sa.Column("discharged_to_concept_id", sa.Integer(), nullable=True),
        sa.Column("discharged_to_source_value", sa.String(50), nullable=True),
        sa.Column("preceding_visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("parent_visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=False),
    )
    op.create_index("idx_visit_detail_person", "visit_detail", ["person_id"])
    op.create_index("idx_visit_detail_visit", "visit_detail", ["visit_occurrence_id"])

    # Create condition_occurrence table
    op.create_table(
        "condition_occurrence",
        sa.Column("condition_occurrence_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("condition_concept_id", sa.Integer(), nullable=False),
        sa.Column("condition_start_date", sa.Date(), nullable=False),
        sa.Column("condition_start_datetime", sa.DateTime(), nullable=True),
        sa.Column("condition_end_date", sa.Date(), nullable=True),
        sa.Column("condition_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("condition_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("condition_status_concept_id", sa.Integer(), nullable=True),
        sa.Column("stop_reason", sa.String(20), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("condition_source_value", sa.String(50), nullable=True),
        sa.Column("condition_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("condition_status_source_value", sa.String(50), nullable=True),
    )
    op.create_index("idx_condition_person_date", "condition_occurrence", ["person_id", "condition_start_date"])
    op.create_index("idx_condition_concept", "condition_occurrence", ["condition_concept_id"])
    op.create_index("idx_condition_visit", "condition_occurrence", ["visit_occurrence_id"])

    # Create drug_exposure table
    op.create_table(
        "drug_exposure",
        sa.Column("drug_exposure_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("drug_concept_id", sa.Integer(), nullable=False),
        sa.Column("drug_exposure_start_date", sa.Date(), nullable=False),
        sa.Column("drug_exposure_start_datetime", sa.DateTime(), nullable=True),
        sa.Column("drug_exposure_end_date", sa.Date(), nullable=False),
        sa.Column("drug_exposure_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("verbatim_end_date", sa.Date(), nullable=True),
        sa.Column("drug_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("stop_reason", sa.String(20), nullable=True),
        sa.Column("refills", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("days_supply", sa.Integer(), nullable=True),
        sa.Column("sig", sa.Text(), nullable=True),
        sa.Column("route_concept_id", sa.Integer(), nullable=True),
        sa.Column("lot_number", sa.String(50), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("drug_source_value", sa.String(50), nullable=True),
        sa.Column("drug_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("route_source_value", sa.String(50), nullable=True),
        sa.Column("dose_unit_source_value", sa.String(50), nullable=True),
    )
    op.create_index("idx_drug_person_date", "drug_exposure", ["person_id", "drug_exposure_start_date"])
    op.create_index("idx_drug_concept", "drug_exposure", ["drug_concept_id"])
    op.create_index("idx_drug_visit", "drug_exposure", ["visit_occurrence_id"])

    # Create procedure_occurrence table
    op.create_table(
        "procedure_occurrence",
        sa.Column("procedure_occurrence_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("procedure_concept_id", sa.Integer(), nullable=False),
        sa.Column("procedure_date", sa.Date(), nullable=False),
        sa.Column("procedure_datetime", sa.DateTime(), nullable=True),
        sa.Column("procedure_end_date", sa.Date(), nullable=True),
        sa.Column("procedure_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("procedure_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("modifier_concept_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("procedure_source_value", sa.String(50), nullable=True),
        sa.Column("procedure_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("modifier_source_value", sa.String(50), nullable=True),
    )
    op.create_index("idx_procedure_person_date", "procedure_occurrence", ["person_id", "procedure_date"])
    op.create_index("idx_procedure_concept", "procedure_occurrence", ["procedure_concept_id"])
    op.create_index("idx_procedure_visit", "procedure_occurrence", ["visit_occurrence_id"])

    # Create device_exposure table
    op.create_table(
        "device_exposure",
        sa.Column("device_exposure_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("device_concept_id", sa.Integer(), nullable=False),
        sa.Column("device_exposure_start_date", sa.Date(), nullable=False),
        sa.Column("device_exposure_start_datetime", sa.DateTime(), nullable=True),
        sa.Column("device_exposure_end_date", sa.Date(), nullable=True),
        sa.Column("device_exposure_end_datetime", sa.DateTime(), nullable=True),
        sa.Column("device_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("unique_device_id", sa.String(255), nullable=True),
        sa.Column("production_id", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("device_source_value", sa.String(50), nullable=True),
        sa.Column("device_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_source_value", sa.String(50), nullable=True),
        sa.Column("unit_source_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_device_person_date", "device_exposure", ["person_id", "device_exposure_start_date"])
    op.create_index("idx_device_concept", "device_exposure", ["device_concept_id"])

    # Create measurement table
    op.create_table(
        "measurement",
        sa.Column("measurement_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("measurement_concept_id", sa.Integer(), nullable=False),
        sa.Column("measurement_date", sa.Date(), nullable=False),
        sa.Column("measurement_datetime", sa.DateTime(), nullable=True),
        sa.Column("measurement_time", sa.String(10), nullable=True),
        sa.Column("measurement_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("operator_concept_id", sa.Integer(), nullable=True),
        sa.Column("value_as_number", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("value_as_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_concept_id", sa.Integer(), nullable=True),
        sa.Column("range_low", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("range_high", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("measurement_source_value", sa.String(50), nullable=True),
        sa.Column("measurement_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_source_value", sa.String(50), nullable=True),
        sa.Column("unit_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("value_source_value", sa.String(50), nullable=True),
        sa.Column("measurement_event_id", sa.BigInteger(), nullable=True),
        sa.Column("meas_event_field_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_measurement_person_date", "measurement", ["person_id", "measurement_date"])
    op.create_index("idx_measurement_concept", "measurement", ["measurement_concept_id"])
    op.create_index("idx_measurement_visit", "measurement", ["visit_occurrence_id"])

    # Create observation table
    op.create_table(
        "observation",
        sa.Column("observation_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("observation_concept_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("observation_datetime", sa.DateTime(), nullable=True),
        sa.Column("observation_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("value_as_number", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("value_as_string", sa.String(60), nullable=True),
        sa.Column("value_as_concept_id", sa.Integer(), nullable=True),
        sa.Column("qualifier_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_concept_id", sa.Integer(), nullable=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("observation_source_value", sa.String(50), nullable=True),
        sa.Column("observation_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("unit_source_value", sa.String(50), nullable=True),
        sa.Column("qualifier_source_value", sa.String(50), nullable=True),
        sa.Column("value_source_value", sa.String(50), nullable=True),
        sa.Column("observation_event_id", sa.BigInteger(), nullable=True),
        sa.Column("obs_event_field_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_observation_person_date", "observation", ["person_id", "observation_date"])
    op.create_index("idx_observation_concept", "observation", ["observation_concept_id"])
    op.create_index("idx_observation_visit", "observation", ["visit_occurrence_id"])

    # Create note table
    op.create_table(
        "note",
        sa.Column("note_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("note_datetime", sa.DateTime(), nullable=True),
        sa.Column("note_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("note_class_concept_id", sa.Integer(), nullable=False),
        sa.Column("note_title", sa.String(250), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("encoding_concept_id", sa.Integer(), nullable=False),
        sa.Column("language_concept_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("provider.provider_id"), nullable=True),
        sa.Column("visit_occurrence_id", sa.BigInteger(), sa.ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=True),
        sa.Column("visit_detail_id", sa.BigInteger(), sa.ForeignKey("visit_detail.visit_detail_id"), nullable=True),
        sa.Column("note_source_value", sa.String(50), nullable=True),
        sa.Column("note_event_id", sa.BigInteger(), nullable=True),
        sa.Column("note_event_field_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_note_person_date", "note", ["person_id", "note_date"])
    op.create_index("idx_note_visit", "note", ["visit_occurrence_id"])

    # Create note_nlp table
    op.create_table(
        "note_nlp",
        sa.Column("note_nlp_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("note_id", sa.BigInteger(), sa.ForeignKey("note.note_id"), nullable=False),
        sa.Column("section_concept_id", sa.Integer(), nullable=True),
        sa.Column("snippet", sa.String(250), nullable=True),
        sa.Column("offset", sa.String(50), nullable=True),
        sa.Column("lexical_variant", sa.String(250), nullable=False),
        sa.Column("note_nlp_concept_id", sa.Integer(), nullable=True),
        sa.Column("note_nlp_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("nlp_system", sa.String(250), nullable=True),
        sa.Column("nlp_date", sa.Date(), nullable=False),
        sa.Column("nlp_datetime", sa.DateTime(), nullable=True),
        sa.Column("term_exists", sa.String(1), nullable=True),
        sa.Column("term_temporal", sa.String(50), nullable=True),
        sa.Column("term_modifiers", sa.String(2000), nullable=True),
    )
    op.create_index("idx_note_nlp_note", "note_nlp", ["note_id"])
    op.create_index("idx_note_nlp_concept", "note_nlp", ["note_nlp_concept_id"])

    # Create specimen table
    op.create_table(
        "specimen",
        sa.Column("specimen_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("specimen_concept_id", sa.Integer(), nullable=False),
        sa.Column("specimen_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("specimen_date", sa.Date(), nullable=False),
        sa.Column("specimen_datetime", sa.DateTime(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("unit_concept_id", sa.Integer(), nullable=True),
        sa.Column("anatomic_site_concept_id", sa.Integer(), nullable=True),
        sa.Column("disease_status_concept_id", sa.Integer(), nullable=True),
        sa.Column("specimen_source_id", sa.String(50), nullable=True),
        sa.Column("specimen_source_value", sa.String(50), nullable=True),
        sa.Column("unit_source_value", sa.String(50), nullable=True),
        sa.Column("anatomic_site_source_value", sa.String(50), nullable=True),
        sa.Column("disease_status_source_value", sa.String(50), nullable=True),
    )
    op.create_index("idx_specimen_person_date", "specimen", ["person_id", "specimen_date"])
    op.create_index("idx_specimen_concept", "specimen", ["specimen_concept_id"])

    # ==========================================================================
    # Health Economics Tables
    # ==========================================================================

    # Create payer_plan_period table
    op.create_table(
        "payer_plan_period",
        sa.Column("payer_plan_period_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("payer_plan_period_start_date", sa.Date(), nullable=False),
        sa.Column("payer_plan_period_end_date", sa.Date(), nullable=False),
        sa.Column("payer_concept_id", sa.Integer(), nullable=True),
        sa.Column("payer_source_value", sa.String(50), nullable=True),
        sa.Column("payer_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("plan_concept_id", sa.Integer(), nullable=True),
        sa.Column("plan_source_value", sa.String(50), nullable=True),
        sa.Column("plan_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("sponsor_concept_id", sa.Integer(), nullable=True),
        sa.Column("sponsor_source_value", sa.String(50), nullable=True),
        sa.Column("sponsor_source_concept_id", sa.Integer(), nullable=True),
        sa.Column("family_source_value", sa.String(50), nullable=True),
        sa.Column("stop_reason_concept_id", sa.Integer(), nullable=True),
        sa.Column("stop_reason_source_value", sa.String(50), nullable=True),
        sa.Column("stop_reason_source_concept_id", sa.Integer(), nullable=True),
    )
    op.create_index("idx_payer_person_date", "payer_plan_period", ["person_id", "payer_plan_period_start_date"])

    # Create cost table
    op.create_table(
        "cost",
        sa.Column("cost_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cost_event_id", sa.BigInteger(), nullable=False),
        sa.Column("cost_domain_id", sa.String(20), nullable=False),
        sa.Column("cost_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("currency_concept_id", sa.Integer(), nullable=True),
        sa.Column("total_charge", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("total_paid", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_by_payer", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_by_patient", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_patient_copay", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_patient_coinsurance", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_patient_deductible", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_by_primary", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_ingredient_cost", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("paid_dispensing_fee", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("payer_plan_period_id", sa.BigInteger(), sa.ForeignKey("payer_plan_period.payer_plan_period_id"), nullable=True),
        sa.Column("amount_allowed", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("revenue_code_concept_id", sa.Integer(), nullable=True),
        sa.Column("revenue_code_source_value", sa.String(50), nullable=True),
        sa.Column("drg_concept_id", sa.Integer(), nullable=True),
        sa.Column("drg_source_value", sa.String(3), nullable=True),
    )
    op.create_index("idx_cost_event", "cost", ["cost_event_id", "cost_domain_id"])

    # ==========================================================================
    # Derived Elements Tables
    # ==========================================================================

    # Create drug_era table
    op.create_table(
        "drug_era",
        sa.Column("drug_era_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("drug_concept_id", sa.Integer(), nullable=False),
        sa.Column("drug_era_start_date", sa.Date(), nullable=False),
        sa.Column("drug_era_end_date", sa.Date(), nullable=False),
        sa.Column("drug_exposure_count", sa.Integer(), nullable=True),
        sa.Column("gap_days", sa.Integer(), nullable=True),
    )
    op.create_index("idx_drug_era_person_date", "drug_era", ["person_id", "drug_era_start_date"])
    op.create_index("idx_drug_era_concept", "drug_era", ["drug_concept_id"])

    # Create dose_era table
    op.create_table(
        "dose_era",
        sa.Column("dose_era_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("drug_concept_id", sa.Integer(), nullable=False),
        sa.Column("unit_concept_id", sa.Integer(), nullable=False),
        sa.Column("dose_value", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("dose_era_start_date", sa.Date(), nullable=False),
        sa.Column("dose_era_end_date", sa.Date(), nullable=False),
    )
    op.create_index("idx_dose_era_person_date", "dose_era", ["person_id", "dose_era_start_date"])
    op.create_index("idx_dose_era_concept", "dose_era", ["drug_concept_id"])

    # Create condition_era table
    op.create_table(
        "condition_era",
        sa.Column("condition_era_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("person_id", sa.BigInteger(), sa.ForeignKey("person.person_id"), nullable=False),
        sa.Column("condition_concept_id", sa.Integer(), nullable=False),
        sa.Column("condition_era_start_date", sa.Date(), nullable=False),
        sa.Column("condition_era_end_date", sa.Date(), nullable=False),
        sa.Column("condition_occurrence_count", sa.Integer(), nullable=True),
    )
    op.create_index("idx_condition_era_person_date", "condition_era", ["person_id", "condition_era_start_date"])
    op.create_index("idx_condition_era_concept", "condition_era", ["condition_concept_id"])

    # ==========================================================================
    # Metadata Tables
    # ==========================================================================

    # Create cdm_source table
    op.create_table(
        "cdm_source",
        sa.Column("cdm_source_name", sa.String(255), primary_key=True),
        sa.Column("cdm_source_abbreviation", sa.String(25), nullable=True),
        sa.Column("cdm_holder", sa.String(255), nullable=True),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("source_documentation_reference", sa.String(255), nullable=True),
        sa.Column("cdm_etl_reference", sa.String(255), nullable=True),
        sa.Column("source_release_date", sa.Date(), nullable=True),
        sa.Column("cdm_release_date", sa.Date(), nullable=True),
        sa.Column("cdm_version", sa.String(10), nullable=True),
        sa.Column("cdm_version_concept_id", sa.Integer(), nullable=False),
        sa.Column("vocabulary_version", sa.String(20), nullable=True),
    )

    # Create metadata table
    op.create_table(
        "metadata",
        sa.Column("metadata_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("metadata_concept_id", sa.Integer(), nullable=False),
        sa.Column("metadata_type_concept_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("value_as_string", sa.String(250), nullable=True),
        sa.Column("value_as_concept_id", sa.Integer(), nullable=True),
        sa.Column("value_as_number", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("metadata_date", sa.Date(), nullable=True),
        sa.Column("metadata_datetime", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_metadata_concept", "metadata", ["metadata_concept_id"])


def downgrade() -> None:
    # ==========================================================================
    # Drop Metadata Tables
    # ==========================================================================
    op.drop_index("idx_metadata_concept", table_name="metadata")
    op.drop_table("metadata")
    op.drop_table("cdm_source")

    # ==========================================================================
    # Drop Derived Elements Tables
    # ==========================================================================
    op.drop_index("idx_condition_era_concept", table_name="condition_era")
    op.drop_index("idx_condition_era_person_date", table_name="condition_era")
    op.drop_table("condition_era")

    op.drop_index("idx_dose_era_concept", table_name="dose_era")
    op.drop_index("idx_dose_era_person_date", table_name="dose_era")
    op.drop_table("dose_era")

    op.drop_index("idx_drug_era_concept", table_name="drug_era")
    op.drop_index("idx_drug_era_person_date", table_name="drug_era")
    op.drop_table("drug_era")

    # ==========================================================================
    # Drop Health Economics Tables
    # ==========================================================================
    op.drop_index("idx_cost_event", table_name="cost")
    op.drop_table("cost")

    op.drop_index("idx_payer_person_date", table_name="payer_plan_period")
    op.drop_table("payer_plan_period")

    # ==========================================================================
    # Drop Clinical Data Tables
    # ==========================================================================
    op.drop_index("idx_specimen_concept", table_name="specimen")
    op.drop_index("idx_specimen_person_date", table_name="specimen")
    op.drop_table("specimen")

    op.drop_index("idx_note_nlp_concept", table_name="note_nlp")
    op.drop_index("idx_note_nlp_note", table_name="note_nlp")
    op.drop_table("note_nlp")

    op.drop_index("idx_note_visit", table_name="note")
    op.drop_index("idx_note_person_date", table_name="note")
    op.drop_table("note")

    op.drop_index("idx_observation_visit", table_name="observation")
    op.drop_index("idx_observation_concept", table_name="observation")
    op.drop_index("idx_observation_person_date", table_name="observation")
    op.drop_table("observation")

    op.drop_index("idx_measurement_visit", table_name="measurement")
    op.drop_index("idx_measurement_concept", table_name="measurement")
    op.drop_index("idx_measurement_person_date", table_name="measurement")
    op.drop_table("measurement")

    op.drop_index("idx_device_concept", table_name="device_exposure")
    op.drop_index("idx_device_person_date", table_name="device_exposure")
    op.drop_table("device_exposure")

    op.drop_index("idx_procedure_visit", table_name="procedure_occurrence")
    op.drop_index("idx_procedure_concept", table_name="procedure_occurrence")
    op.drop_index("idx_procedure_person_date", table_name="procedure_occurrence")
    op.drop_table("procedure_occurrence")

    op.drop_index("idx_drug_visit", table_name="drug_exposure")
    op.drop_index("idx_drug_concept", table_name="drug_exposure")
    op.drop_index("idx_drug_person_date", table_name="drug_exposure")
    op.drop_table("drug_exposure")

    op.drop_index("idx_condition_visit", table_name="condition_occurrence")
    op.drop_index("idx_condition_concept", table_name="condition_occurrence")
    op.drop_index("idx_condition_person_date", table_name="condition_occurrence")
    op.drop_table("condition_occurrence")

    op.drop_index("idx_visit_detail_visit", table_name="visit_detail")
    op.drop_index("idx_visit_detail_person", table_name="visit_detail")
    op.drop_table("visit_detail")

    op.drop_index("idx_visit_concept", table_name="visit_occurrence")
    op.drop_index("idx_visit_person_date", table_name="visit_occurrence")
    op.drop_table("visit_occurrence")

    op.drop_index("idx_observation_period_person", table_name="observation_period")
    op.drop_table("observation_period")

    op.drop_table("death")

    op.drop_index("idx_person_location", table_name="person")
    op.drop_index("idx_person_ethnicity", table_name="person")
    op.drop_index("idx_person_race", table_name="person")
    op.drop_index("idx_person_gender", table_name="person")
    op.drop_table("person")

    # ==========================================================================
    # Drop Health System Data Tables
    # ==========================================================================
    op.drop_index("idx_provider_specialty", table_name="provider")
    op.drop_table("provider")

    op.drop_table("care_site")

    op.drop_index("idx_location_zip", table_name="location")
    op.drop_table("location")
