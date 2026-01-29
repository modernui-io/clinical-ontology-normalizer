"""OMOP CDM v5.4 SQLAlchemy Models.

This module defines SQLAlchemy models for the OHDSI OMOP Common Data Model
version 5.4. These models represent the standardized clinical data tables
used for observational health data analytics.

Reference: https://ohdsi.github.io/CommonDataModel/cdm54.html

Tables Implemented:
    Clinical Data:
        - person: Patient demographics
        - observation_period: Time periods with data
        - visit_occurrence: Healthcare encounters
        - visit_detail: Detailed encounter information
        - condition_occurrence: Diagnoses/conditions
        - drug_exposure: Medication administrations
        - procedure_occurrence: Clinical procedures
        - device_exposure: Device usage
        - measurement: Lab results and vitals
        - observation: Clinical observations
        - death: Death information
        - note: Clinical notes
        - note_nlp: NLP-extracted entities
        - specimen: Biological specimens

    Health System Data:
        - location: Geographic locations
        - care_site: Healthcare facilities
        - provider: Healthcare providers

    Health Economics:
        - payer_plan_period: Insurance coverage
        - cost: Healthcare costs

    Derived Elements:
        - drug_era: Drug exposure periods
        - condition_era: Condition periods

Usage:
    from app.models.omop import Person, VisitOccurrence, ConditionOccurrence

    # Create a new person
    person = Person(
        person_id=1,
        gender_concept_id=8507,
        year_of_birth=1980,
        race_concept_id=8527,
        ethnicity_concept_id=38003564
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    pass


# =============================================================================
# Concept Reference Pattern
# =============================================================================


@dataclass
class ConceptReference:
    """Generic concept reference following OMOP CDM pattern.

    This pattern appears throughout OMOP CDM tables where a standardized concept
    is paired with its original source value and an optional source concept ID.

    OMOP CDM Pattern:
        - concept_id: The standardized OMOP concept identifier
        - source_value: The original value from the source data
        - source_concept_id: The concept ID representing the source coding system

    This dataclass is used for:
        1. Documentation of the pattern
        2. Type hints in service/API layers
        3. Data transfer between layers

    Note: SQLAlchemy models still define columns explicitly for ORM compatibility.
    Use concept_columns() factory to generate column definitions with reduced boilerplate.

    Usage in Python code:
        condition_ref = ConceptReference(
            concept_id=201826,  # Type 2 Diabetes
            source_value="E11.9",
            source_concept_id=45576876
        )

    Tables using this pattern:
        - Person (gender, race, ethnicity)
        - Provider (specialty, gender)
        - Death (cause)
        - VisitOccurrence (visit)
        - VisitDetail (visit_detail, admitted_from, discharged_to)
        - ConditionOccurrence (condition, condition_status)
        - DrugExposure (drug, route)
        - ProcedureOccurrence (procedure, modifier)
        - DeviceExposure (device, unit)
        - Measurement (measurement, unit)
        - Observation (observation, unit, qualifier)
        - Specimen (specimen)
        - PayerPlanPeriod (payer, plan, sponsor, stop_reason)
    """

    concept_id: int
    source_value: str | None = None
    source_concept_id: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "concept_id": self.concept_id,
            "source_value": self.source_value,
            "source_concept_id": self.source_concept_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConceptReference":
        """Create from dictionary."""
        return cls(
            concept_id=data["concept_id"],
            source_value=data.get("source_value"),
            source_concept_id=data.get("source_concept_id"),
        )


def concept_columns(
    prefix: str,
    *,
    concept_id_required: bool = True,
    source_value_length: int = 50,
) -> tuple:
    """Factory function to generate OMOP concept column definitions.

    This reduces boilerplate for the repeated pattern of:
        - {prefix}_concept_id
        - {prefix}_source_value
        - {prefix}_source_concept_id

    Args:
        prefix: The column name prefix (e.g., 'condition', 'drug', 'procedure')
        concept_id_required: Whether concept_id is required (nullable=False)
        source_value_length: Max length of source_value string column

    Returns:
        Tuple of (concept_id_column, source_value_column, source_concept_id_column)

    Example:
        # In model definition:
        condition_concept_id, condition_source_value, condition_source_concept_id = (
            concept_columns("condition")
        )

    Note: This is a documentation helper. Due to SQLAlchemy's requirement for
    explicit column definitions in model classes, the actual column definitions
    remain inline in the models. This function serves as a reference pattern
    and can be used in tests or dynamic model generation scenarios.
    """
    concept_id = mapped_column(Integer, nullable=not concept_id_required)
    source_value = mapped_column(String(source_value_length))
    source_concept_id = mapped_column(Integer)

    return concept_id, source_value, source_concept_id


def extract_concept_reference(
    model,
    prefix: str,
) -> ConceptReference:
    """Extract a ConceptReference from a model instance.

    Args:
        model: SQLAlchemy model instance
        prefix: The concept prefix (e.g., 'condition', 'drug')

    Returns:
        ConceptReference with values from the model

    Example:
        condition = ConditionOccurrence(...)
        ref = extract_concept_reference(condition, "condition")
        # ref.concept_id == condition.condition_concept_id
    """
    return ConceptReference(
        concept_id=getattr(model, f"{prefix}_concept_id"),
        source_value=getattr(model, f"{prefix}_source_value", None),
        source_concept_id=getattr(model, f"{prefix}_source_concept_id", None),
    )


def set_concept_reference(
    model,
    prefix: str,
    ref: ConceptReference,
) -> None:
    """Set concept reference fields on a model instance.

    Args:
        model: SQLAlchemy model instance
        prefix: The concept prefix (e.g., 'condition', 'drug')
        ref: ConceptReference with values to set

    Example:
        ref = ConceptReference(concept_id=201826, source_value="E11.9")
        set_concept_reference(condition, "condition", ref)
    """
    setattr(model, f"{prefix}_concept_id", ref.concept_id)
    if hasattr(model, f"{prefix}_source_value"):
        setattr(model, f"{prefix}_source_value", ref.source_value)
    if hasattr(model, f"{prefix}_source_concept_id"):
        setattr(model, f"{prefix}_source_concept_id", ref.source_concept_id)


# =============================================================================
# Health System Data Tables
# =============================================================================


class Location(Base):
    """Geographic location information.

    Represents physical addresses used by care sites and patients.
    Based on OMOP CDM v5.4 LOCATION table.
    """

    __tablename__ = "location"

    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address_1: Mapped[str | None] = mapped_column(String(50))
    address_2: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(50))
    state: Mapped[str | None] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(9))
    county: Mapped[str | None] = mapped_column(String(20))
    location_source_value: Mapped[str | None] = mapped_column(String(50))
    country_concept_id: Mapped[int | None] = mapped_column(Integer)
    country_source_value: Mapped[str | None] = mapped_column(String(80))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(precision=9, scale=6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(precision=9, scale=6))

    __table_args__ = (
        Index("idx_location_zip", "zip"),
    )


class CareSite(Base):
    """Healthcare facility information.

    Represents hospitals, clinics, and other care delivery locations.
    Based on OMOP CDM v5.4 CARE_SITE table.
    """

    __tablename__ = "care_site"

    care_site_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    care_site_name: Mapped[str | None] = mapped_column(String(255))
    place_of_service_concept_id: Mapped[int | None] = mapped_column(Integer)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.location_id"))
    care_site_source_value: Mapped[str | None] = mapped_column(String(50))
    place_of_service_source_value: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    location: Mapped["Location | None"] = relationship("Location")


class Provider(Base):
    """Healthcare provider information.

    Represents physicians, nurses, and other healthcare professionals.
    Based on OMOP CDM v5.4 PROVIDER table.
    """

    __tablename__ = "provider"

    provider_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_name: Mapped[str | None] = mapped_column(String(255))
    npi: Mapped[str | None] = mapped_column(String(20))
    dea: Mapped[str | None] = mapped_column(String(20))
    specialty_concept_id: Mapped[int | None] = mapped_column(Integer)
    care_site_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("care_site.care_site_id"))
    year_of_birth: Mapped[int | None] = mapped_column(Integer)
    gender_concept_id: Mapped[int | None] = mapped_column(Integer)
    provider_source_value: Mapped[str | None] = mapped_column(String(50))
    specialty_source_value: Mapped[str | None] = mapped_column(String(50))
    specialty_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    gender_source_value: Mapped[str | None] = mapped_column(String(50))
    gender_source_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    care_site: Mapped["CareSite | None"] = relationship("CareSite")

    __table_args__ = (
        Index("idx_provider_specialty", "specialty_concept_id"),
    )


# =============================================================================
# Clinical Data Tables
# =============================================================================


class Person(Base):
    """Patient demographic information.

    The central table of the OMOP CDM representing individual patients.
    Based on OMOP CDM v5.4 PERSON table.
    """

    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gender_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    year_of_birth: Mapped[int] = mapped_column(Integer, nullable=False)
    month_of_birth: Mapped[int | None] = mapped_column(Integer)
    day_of_birth: Mapped[int | None] = mapped_column(Integer)
    birth_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    race_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ethnicity_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("location.location_id"))
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    care_site_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("care_site.care_site_id"))
    person_source_value: Mapped[str | None] = mapped_column(String(50))
    gender_source_value: Mapped[str | None] = mapped_column(String(50))
    gender_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    race_source_value: Mapped[str | None] = mapped_column(String(50))
    race_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    ethnicity_source_value: Mapped[str | None] = mapped_column(String(50))
    ethnicity_source_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    location: Mapped["Location | None"] = relationship("Location")
    provider: Mapped["Provider | None"] = relationship("Provider")
    care_site: Mapped["CareSite | None"] = relationship("CareSite")

    __table_args__ = (
        Index("idx_person_gender", "gender_concept_id"),
        Index("idx_person_race", "race_concept_id"),
        Index("idx_person_ethnicity", "ethnicity_concept_id"),
        Index("idx_person_location", "location_id"),
    )


class Death(Base):
    """Patient death information.

    Records death date, cause, and type for deceased patients.
    Based on OMOP CDM v5.4 DEATH table.
    """

    __tablename__ = "death"

    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), primary_key=True)
    death_date: Mapped[date] = mapped_column(Date, nullable=False)
    death_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    death_type_concept_id: Mapped[int | None] = mapped_column(Integer)
    cause_concept_id: Mapped[int | None] = mapped_column(Integer)
    cause_source_value: Mapped[str | None] = mapped_column(String(50))
    cause_source_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")


class ObservationPeriod(Base):
    """Time periods with observed data for a person.

    Defines the span of time when a person has data in the database.
    Based on OMOP CDM v5.4 OBSERVATION_PERIOD table.
    """

    __tablename__ = "observation_period"

    observation_period_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    observation_period_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    observation_period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_observation_period_person", "person_id"),
    )


class VisitOccurrence(Base):
    """Healthcare encounter/visit information.

    Records visits to healthcare providers including inpatient stays,
    outpatient visits, emergency room visits, etc.
    Based on OMOP CDM v5.4 VISIT_OCCURRENCE table.
    """

    __tablename__ = "visit_occurrence"

    visit_occurrence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    visit_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    visit_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    visit_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    care_site_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("care_site.care_site_id"))
    visit_source_value: Mapped[str | None] = mapped_column(String(50))
    visit_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    admitted_from_concept_id: Mapped[int | None] = mapped_column(Integer)
    admitted_from_source_value: Mapped[str | None] = mapped_column(String(50))
    discharged_to_concept_id: Mapped[int | None] = mapped_column(Integer)
    discharged_to_source_value: Mapped[str | None] = mapped_column(String(50))
    preceding_visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    care_site: Mapped["CareSite | None"] = relationship("CareSite")

    __table_args__ = (
        Index("idx_visit_person_date", "person_id", "visit_start_date"),
        Index("idx_visit_concept", "visit_concept_id"),
    )


class VisitDetail(Base):
    """Detailed visit/encounter information.

    Provides finer-grained detail about visits, such as transfers
    between units during an inpatient stay.
    Based on OMOP CDM v5.4 VISIT_DETAIL table.
    """

    __tablename__ = "visit_detail"

    visit_detail_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    visit_detail_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_detail_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_detail_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    visit_detail_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_detail_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    visit_detail_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    care_site_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("care_site.care_site_id"))
    visit_detail_source_value: Mapped[str | None] = mapped_column(String(50))
    visit_detail_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    admitted_from_concept_id: Mapped[int | None] = mapped_column(Integer)
    admitted_from_source_value: Mapped[str | None] = mapped_column(String(50))
    discharged_to_concept_id: Mapped[int | None] = mapped_column(Integer)
    discharged_to_source_value: Mapped[str | None] = mapped_column(String(50))
    preceding_visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    parent_visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    visit_occurrence_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"), nullable=False)

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    care_site: Mapped["CareSite | None"] = relationship("CareSite")
    visit_occurrence: Mapped["VisitOccurrence"] = relationship("VisitOccurrence")

    __table_args__ = (
        Index("idx_visit_detail_person", "person_id"),
        Index("idx_visit_detail_visit", "visit_occurrence_id"),
    )


class ConditionOccurrence(Base):
    """Patient condition/diagnosis information.

    Records diagnoses, problems, and conditions for patients.
    Based on OMOP CDM v5.4 CONDITION_OCCURRENCE table.
    """

    __tablename__ = "condition_occurrence"

    condition_occurrence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    condition_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    condition_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    condition_end_date: Mapped[date | None] = mapped_column(Date)
    condition_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    condition_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_status_concept_id: Mapped[int | None] = mapped_column(Integer)
    stop_reason: Mapped[str | None] = mapped_column(String(20))
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    condition_source_value: Mapped[str | None] = mapped_column(String(50))
    condition_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    condition_status_source_value: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_condition_person_date", "person_id", "condition_start_date"),
        Index("idx_condition_concept", "condition_concept_id"),
        Index("idx_condition_visit", "visit_occurrence_id"),
    )


class DrugExposure(Base):
    """Patient medication exposure information.

    Records drug/medication exposures including prescriptions,
    dispensings, and administrations.
    Based on OMOP CDM v5.4 DRUG_EXPOSURE table.
    """

    __tablename__ = "drug_exposure"

    drug_exposure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    drug_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    drug_exposure_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    drug_exposure_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    drug_exposure_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    drug_exposure_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    verbatim_end_date: Mapped[date | None] = mapped_column(Date)
    drug_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String(20))
    refills: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(precision=10, scale=2))
    days_supply: Mapped[int | None] = mapped_column(Integer)
    sig: Mapped[str | None] = mapped_column(Text)
    route_concept_id: Mapped[int | None] = mapped_column(Integer)
    lot_number: Mapped[str | None] = mapped_column(String(50))
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    drug_source_value: Mapped[str | None] = mapped_column(String(50))
    drug_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    route_source_value: Mapped[str | None] = mapped_column(String(50))
    dose_unit_source_value: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_drug_person_date", "person_id", "drug_exposure_start_date"),
        Index("idx_drug_concept", "drug_concept_id"),
        Index("idx_drug_visit", "visit_occurrence_id"),
    )


class ProcedureOccurrence(Base):
    """Patient procedure information.

    Records clinical procedures performed on patients.
    Based on OMOP CDM v5.4 PROCEDURE_OCCURRENCE table.
    """

    __tablename__ = "procedure_occurrence"

    procedure_occurrence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    procedure_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    procedure_date: Mapped[date] = mapped_column(Date, nullable=False)
    procedure_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    procedure_end_date: Mapped[date | None] = mapped_column(Date)
    procedure_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    procedure_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    modifier_concept_id: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int | None] = mapped_column(Integer)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    procedure_source_value: Mapped[str | None] = mapped_column(String(50))
    procedure_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    modifier_source_value: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_procedure_person_date", "person_id", "procedure_date"),
        Index("idx_procedure_concept", "procedure_concept_id"),
        Index("idx_procedure_visit", "visit_occurrence_id"),
    )


class DeviceExposure(Base):
    """Patient device exposure information.

    Records medical devices used by or on patients.
    Based on OMOP CDM v5.4 DEVICE_EXPOSURE table.
    """

    __tablename__ = "device_exposure"

    device_exposure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    device_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    device_exposure_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    device_exposure_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    device_exposure_end_date: Mapped[date | None] = mapped_column(Date)
    device_exposure_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    device_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_device_id: Mapped[str | None] = mapped_column(String(255))
    production_id: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int | None] = mapped_column(Integer)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    device_source_value: Mapped[str | None] = mapped_column(String(50))
    device_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_source_value: Mapped[str | None] = mapped_column(String(50))
    unit_source_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_device_person_date", "person_id", "device_exposure_start_date"),
        Index("idx_device_concept", "device_concept_id"),
    )


class Measurement(Base):
    """Patient measurement information.

    Records lab results, vital signs, and other clinical measurements.
    Based on OMOP CDM v5.4 MEASUREMENT table.
    """

    __tablename__ = "measurement"

    measurement_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    measurement_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    measurement_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    measurement_time: Mapped[str | None] = mapped_column(String(10))
    measurement_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_concept_id: Mapped[int | None] = mapped_column(Integer)
    value_as_number: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6))
    value_as_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_concept_id: Mapped[int | None] = mapped_column(Integer)
    range_low: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6))
    range_high: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6))
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    measurement_source_value: Mapped[str | None] = mapped_column(String(50))
    measurement_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_source_value: Mapped[str | None] = mapped_column(String(50))
    unit_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    value_source_value: Mapped[str | None] = mapped_column(String(50))
    measurement_event_id: Mapped[int | None] = mapped_column(BigInteger)
    meas_event_field_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_measurement_person_date", "person_id", "measurement_date"),
        Index("idx_measurement_concept", "measurement_concept_id"),
        Index("idx_measurement_visit", "visit_occurrence_id"),
    )


class Observation(Base):
    """Patient observation information.

    Records clinical observations not captured elsewhere (e.g., social
    history, family history, clinical findings).
    Based on OMOP CDM v5.4 OBSERVATION table.
    """

    __tablename__ = "observation"

    observation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    observation_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    observation_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    observation_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    value_as_number: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6))
    value_as_string: Mapped[str | None] = mapped_column(String(60))
    value_as_concept_id: Mapped[int | None] = mapped_column(Integer)
    qualifier_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_concept_id: Mapped[int | None] = mapped_column(Integer)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    observation_source_value: Mapped[str | None] = mapped_column(String(50))
    observation_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    unit_source_value: Mapped[str | None] = mapped_column(String(50))
    qualifier_source_value: Mapped[str | None] = mapped_column(String(50))
    value_source_value: Mapped[str | None] = mapped_column(String(50))
    observation_event_id: Mapped[int | None] = mapped_column(BigInteger)
    obs_event_field_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_observation_person_date", "person_id", "observation_date"),
        Index("idx_observation_concept", "observation_concept_id"),
        Index("idx_observation_visit", "visit_occurrence_id"),
    )


class Note(Base):
    """Clinical note information.

    Records clinical notes and documents.
    Based on OMOP CDM v5.4 NOTE table.
    """

    __tablename__ = "note"

    note_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    note_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    note_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note_class_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note_title: Mapped[str | None] = mapped_column(String(250))
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    encoding_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    language_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("provider.provider_id"))
    visit_occurrence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_occurrence.visit_occurrence_id"))
    visit_detail_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("visit_detail.visit_detail_id"))
    note_source_value: Mapped[str | None] = mapped_column(String(50))
    note_event_id: Mapped[int | None] = mapped_column(BigInteger)
    note_event_field_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")
    provider: Mapped["Provider | None"] = relationship("Provider")
    visit_occurrence: Mapped["VisitOccurrence | None"] = relationship("VisitOccurrence")
    visit_detail: Mapped["VisitDetail | None"] = relationship("VisitDetail")

    __table_args__ = (
        Index("idx_note_person_date", "person_id", "note_date"),
        Index("idx_note_visit", "visit_occurrence_id"),
    )


class NoteNlp(Base):
    """NLP-extracted entities from clinical notes.

    Records entities extracted through natural language processing.
    Based on OMOP CDM v5.4 NOTE_NLP table.
    """

    __tablename__ = "note_nlp"

    note_nlp_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    note_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("note.note_id"), nullable=False)
    section_concept_id: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str | None] = mapped_column(String(250))
    offset: Mapped[str | None] = mapped_column(String(50))
    lexical_variant: Mapped[str] = mapped_column(String(250), nullable=False)
    note_nlp_concept_id: Mapped[int | None] = mapped_column(Integer)
    note_nlp_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    nlp_system: Mapped[str | None] = mapped_column(String(250))
    nlp_date: Mapped[date] = mapped_column(Date, nullable=False)
    nlp_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    term_exists: Mapped[str | None] = mapped_column(String(1))
    term_temporal: Mapped[str | None] = mapped_column(String(50))
    term_modifiers: Mapped[str | None] = mapped_column(String(2000))

    # Relationships
    note: Mapped["Note"] = relationship("Note")

    __table_args__ = (
        Index("idx_note_nlp_note", "note_id"),
        Index("idx_note_nlp_concept", "note_nlp_concept_id"),
    )


class Specimen(Base):
    """Biological specimen information.

    Records biological specimens collected from patients.
    Based on OMOP CDM v5.4 SPECIMEN table.
    """

    __tablename__ = "specimen"

    specimen_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    specimen_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    specimen_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    specimen_date: Mapped[date] = mapped_column(Date, nullable=False)
    specimen_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(precision=10, scale=2))
    unit_concept_id: Mapped[int | None] = mapped_column(Integer)
    anatomic_site_concept_id: Mapped[int | None] = mapped_column(Integer)
    disease_status_concept_id: Mapped[int | None] = mapped_column(Integer)
    specimen_source_id: Mapped[str | None] = mapped_column(String(50))
    specimen_source_value: Mapped[str | None] = mapped_column(String(50))
    unit_source_value: Mapped[str | None] = mapped_column(String(50))
    anatomic_site_source_value: Mapped[str | None] = mapped_column(String(50))
    disease_status_source_value: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_specimen_person_date", "person_id", "specimen_date"),
        Index("idx_specimen_concept", "specimen_concept_id"),
    )


# =============================================================================
# Health Economics Tables
# =============================================================================


class PayerPlanPeriod(Base):
    """Patient insurance/payer coverage periods.

    Records periods of insurance coverage for patients.
    Based on OMOP CDM v5.4 PAYER_PLAN_PERIOD table.
    """

    __tablename__ = "payer_plan_period"

    payer_plan_period_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    payer_plan_period_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    payer_plan_period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    payer_concept_id: Mapped[int | None] = mapped_column(Integer)
    payer_source_value: Mapped[str | None] = mapped_column(String(50))
    payer_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    plan_concept_id: Mapped[int | None] = mapped_column(Integer)
    plan_source_value: Mapped[str | None] = mapped_column(String(50))
    plan_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    sponsor_concept_id: Mapped[int | None] = mapped_column(Integer)
    sponsor_source_value: Mapped[str | None] = mapped_column(String(50))
    sponsor_source_concept_id: Mapped[int | None] = mapped_column(Integer)
    family_source_value: Mapped[str | None] = mapped_column(String(50))
    stop_reason_concept_id: Mapped[int | None] = mapped_column(Integer)
    stop_reason_source_value: Mapped[str | None] = mapped_column(String(50))
    stop_reason_source_concept_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_payer_person_date", "person_id", "payer_plan_period_start_date"),
    )


class Cost(Base):
    """Healthcare cost information.

    Records costs associated with clinical events.
    Based on OMOP CDM v5.4 COST table.
    """

    __tablename__ = "cost"

    cost_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cost_event_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_domain_id: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_concept_id: Mapped[int | None] = mapped_column(Integer)
    total_charge: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    total_paid: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_by_payer: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_by_patient: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_patient_copay: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_patient_coinsurance: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_patient_deductible: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_by_primary: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_ingredient_cost: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    paid_dispensing_fee: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    payer_plan_period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("payer_plan_period.payer_plan_period_id"))
    amount_allowed: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2))
    revenue_code_concept_id: Mapped[int | None] = mapped_column(Integer)
    revenue_code_source_value: Mapped[str | None] = mapped_column(String(50))
    drg_concept_id: Mapped[int | None] = mapped_column(Integer)
    drg_source_value: Mapped[str | None] = mapped_column(String(3))

    # Relationships
    payer_plan_period: Mapped["PayerPlanPeriod | None"] = relationship("PayerPlanPeriod")

    __table_args__ = (
        Index("idx_cost_event", "cost_event_id", "cost_domain_id"),
    )


# =============================================================================
# Derived Elements Tables
# =============================================================================


class DrugEra(Base):
    """Derived drug exposure periods.

    Aggregated periods of drug exposure derived from drug_exposure.
    Based on OMOP CDM v5.4 DRUG_ERA table.
    """

    __tablename__ = "drug_era"

    drug_era_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    drug_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    drug_era_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    drug_era_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    drug_exposure_count: Mapped[int | None] = mapped_column(Integer)
    gap_days: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_drug_era_person_date", "person_id", "drug_era_start_date"),
        Index("idx_drug_era_concept", "drug_concept_id"),
    )


class DoseEra(Base):
    """Derived dose-specific drug exposure periods.

    Aggregated periods of drug exposure at specific doses.
    Based on OMOP CDM v5.4 DOSE_ERA table.
    """

    __tablename__ = "dose_era"

    dose_era_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    drug_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dose_value: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    dose_era_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    dose_era_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_dose_era_person_date", "person_id", "dose_era_start_date"),
        Index("idx_dose_era_concept", "drug_concept_id"),
    )


class ConditionEra(Base):
    """Derived condition/diagnosis periods.

    Aggregated periods of conditions derived from condition_occurrence.
    Based on OMOP CDM v5.4 CONDITION_ERA table.
    """

    __tablename__ = "condition_era"

    condition_era_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.person_id"), nullable=False)
    condition_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_era_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    condition_era_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    condition_occurrence_count: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    person: Mapped["Person"] = relationship("Person")

    __table_args__ = (
        Index("idx_condition_era_person_date", "person_id", "condition_era_start_date"),
        Index("idx_condition_era_concept", "condition_concept_id"),
    )


# =============================================================================
# Metadata Tables
# =============================================================================


class CdmSource(Base):
    """CDM source database metadata.

    Records information about the source database and CDM instance.
    Based on OMOP CDM v5.4 CDM_SOURCE table.
    """

    __tablename__ = "cdm_source"

    cdm_source_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    cdm_source_abbreviation: Mapped[str | None] = mapped_column(String(25))
    cdm_holder: Mapped[str | None] = mapped_column(String(255))
    source_description: Mapped[str | None] = mapped_column(Text)
    source_documentation_reference: Mapped[str | None] = mapped_column(String(255))
    cdm_etl_reference: Mapped[str | None] = mapped_column(String(255))
    source_release_date: Mapped[date | None] = mapped_column(Date)
    cdm_release_date: Mapped[date | None] = mapped_column(Date)
    cdm_version: Mapped[str | None] = mapped_column(String(10))
    cdm_version_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vocabulary_version: Mapped[str | None] = mapped_column(String(20))


class Metadata(Base):
    """General metadata storage.

    Stores key-value metadata about the CDM instance.
    Based on OMOP CDM v5.4 METADATA table.
    """

    __tablename__ = "metadata"

    metadata_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    metadata_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_type_concept_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    value_as_string: Mapped[str | None] = mapped_column(String(250))
    value_as_concept_id: Mapped[int | None] = mapped_column(Integer)
    value_as_number: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6))
    metadata_date: Mapped[date | None] = mapped_column(Date)
    metadata_datetime: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_metadata_concept", "metadata_concept_id"),
    )
