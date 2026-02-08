#!/usr/bin/env python3
"""Seed script to create trial-ready demo patients via FHIR import.

Creates 18 realistic patients across Regeneron trial categories:
  - EYLEA HD (DME): 5 eligible patients with T2DM + DME + HbA1c < 12%
  - Dupixent (AD): 5 eligible patients with atopic dermatitis
  - Libtayo (CSCC): 4 eligible patients with cutaneous SCC
  - Ineligible: 4 patients who fail exclusion criteria

Each patient is imported as a FHIR R4 Bundle through FHIRImportService.import_bundle()
so that ClinicalFacts, KGNodes, and KGEdges are created via the standard pipeline.

Usage:
    python3 -m scripts.seed_trial_patients

Or from the backend directory:
    python3 scripts/seed_trial_patients.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker, init_db
from app.services.fhir_import import FHIRImportService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# FHIR Resource Helpers
# =============================================================================


def _patient_resource(
    patient_id: str,
    given: str,
    family: str,
    gender: str,
    birth_date: str,
    mrn: str,
) -> dict[str, Any]:
    """Build a FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "system": "http://hospital.example.org/mrn",
                "value": mrn,
            }
        ],
        "name": [{"given": [given], "family": family}],
        "gender": gender,
        "birthDate": birth_date,
    }


def _condition_resource(
    code: str,
    display: str,
    system: str = "http://hl7.org/fhir/sid/icd-10-cm",
    onset_date: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """Build a FHIR Condition resource."""
    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "id": str(uuid4()),
        "code": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": status,
                }
            ]
        },
    }
    if onset_date:
        resource["onsetDateTime"] = onset_date
    return resource


def _observation_resource(
    code: str,
    display: str,
    value: float,
    unit: str,
    system: str = "http://loinc.org",
    effective_date: str | None = None,
    category_code: str = "laboratory",
) -> dict[str, Any]:
    """Build a FHIR Observation resource (lab/vital)."""
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": str(uuid4()),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": category_code,
                    }
                ]
            }
        ],
        "code": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
        "valueQuantity": {"value": value, "unit": unit},
    }
    if effective_date:
        resource["effectiveDateTime"] = effective_date
    return resource


def _medication_resource(
    code: str,
    display: str,
    system: str = "http://www.nlm.nih.gov/research/umls/rxnorm",
    status: str = "active",
    authored_on: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR MedicationRequest resource."""
    resource: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": str(uuid4()),
        "status": status,
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
    }
    if authored_on:
        resource["authoredOn"] = authored_on
    return resource


def _procedure_resource(
    code: str,
    display: str,
    system: str = "http://snomed.info/sct",
    performed_date: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR Procedure resource."""
    resource: dict[str, Any] = {
        "resourceType": "Procedure",
        "id": str(uuid4()),
        "status": "completed",
        "code": {
            "coding": [{"system": system, "code": code, "display": display}],
            "text": display,
        },
    }
    if performed_date:
        resource["performedDateTime"] = performed_date
    return resource


def _bundle(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap resources in a FHIR R4 Bundle."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in entries],
    }


# =============================================================================
# Patient Definitions
# =============================================================================


def _eylea_patients() -> list[tuple[str, dict[str, Any]]]:
    """5 EYLEA HD eligible patients: T2DM + DME + HbA1c < 12%."""
    patients = []

    # Patient 1: 62yo male, well-controlled diabetes
    patients.append((
        "eylea-pt-001",
        _bundle([
            _patient_resource("eylea-pt-001", "Robert", "Chen", "male", "1963-08-14", "MRN-E001"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2015-03-10"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2024-06-15"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2024-06-15"),
            _observation_resource("4548-4", "Hemoglobin A1c", 7.8, "%", effective_date="2025-11-20"),
            _observation_resource("2345-7", "Glucose [Mass/volume] in Serum or Plasma", 145.0, "mg/dL", effective_date="2025-11-20"),
            _observation_resource("8462-4", "Diastolic blood pressure", 82.0, "mmHg", category_code="vital-signs", effective_date="2025-11-20"),
            _medication_resource("860975", "Metformin 500 MG", authored_on="2015-04-01"),
            _procedure_resource("314972000", "Fundus examination", performed_date="2024-06-15"),
        ]),
    ))

    # Patient 2: 55yo female, moderate HbA1c
    patients.append((
        "eylea-pt-002",
        _bundle([
            _patient_resource("eylea-pt-002", "Maria", "Santos", "female", "1970-11-22", "MRN-E002"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2018-01-05"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2025-02-10"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2025-02-10"),
            _condition_resource("I10", "Essential hypertension", onset_date="2017-06-20"),
            _observation_resource("4548-4", "Hemoglobin A1c", 8.5, "%", effective_date="2025-10-15"),
            _observation_resource("2345-7", "Glucose [Mass/volume] in Serum or Plasma", 168.0, "mg/dL", effective_date="2025-10-15"),
            _medication_resource("860975", "Metformin 500 MG", authored_on="2018-02-01"),
            _medication_resource("213169", "Sitagliptin 100 MG", authored_on="2020-07-15"),
            _procedure_resource("314972000", "Fundus examination", performed_date="2025-02-10"),
        ]),
    ))

    # Patient 3: 71yo male, borderline HbA1c (under 12 threshold)
    patients.append((
        "eylea-pt-003",
        _bundle([
            _patient_resource("eylea-pt-003", "James", "Williams", "male", "1954-05-30", "MRN-E003"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2010-09-12"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2024-11-01"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2024-11-01"),
            _condition_resource("E78.5", "Hyperlipidemia, unspecified", onset_date="2012-04-18"),
            _observation_resource("4548-4", "Hemoglobin A1c", 10.2, "%", effective_date="2025-09-10"),
            _observation_resource("8480-6", "Systolic blood pressure", 138.0, "mmHg", category_code="vital-signs", effective_date="2025-09-10"),
            _medication_resource("1373463", "Insulin glargine 100 UNT/ML", authored_on="2016-03-22"),
            _medication_resource("860975", "Metformin 500 MG", authored_on="2010-10-01"),
        ]),
    ))

    # Patient 4: 48yo female, recent DME diagnosis
    patients.append((
        "eylea-pt-004",
        _bundle([
            _patient_resource("eylea-pt-004", "Aisha", "Patel", "female", "1977-03-19", "MRN-E004"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2019-12-08"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2025-08-20"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2025-08-20"),
            _observation_resource("4548-4", "Hemoglobin A1c", 7.1, "%", effective_date="2025-12-03"),
            _observation_resource("2345-7", "Glucose [Mass/volume] in Serum or Plasma", 128.0, "mg/dL", effective_date="2025-12-03"),
            _medication_resource("860975", "Metformin 500 MG", authored_on="2020-01-15"),
            _procedure_resource("314972000", "Fundus examination", performed_date="2025-08-20"),
        ]),
    ))

    # Patient 5: 66yo male, stable on insulin
    patients.append((
        "eylea-pt-005",
        _bundle([
            _patient_resource("eylea-pt-005", "William", "Jackson", "male", "1959-12-05", "MRN-E005"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2012-07-14"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2025-01-18"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2025-01-18"),
            _condition_resource("I10", "Essential hypertension", onset_date="2014-02-28"),
            _observation_resource("4548-4", "Hemoglobin A1c", 8.9, "%", effective_date="2025-10-22"),
            _medication_resource("1373463", "Insulin glargine 100 UNT/ML", authored_on="2017-05-10"),
            _medication_resource("316672", "Lisinopril 10 MG", authored_on="2014-03-15"),
            _procedure_resource("314972000", "Fundus examination", performed_date="2025-01-18"),
        ]),
    ))

    return patients


def _dupixent_patients() -> list[tuple[str, dict[str, Any]]]:
    """5 Dupixent eligible patients: Atopic dermatitis, no cancer/TB."""
    patients = []

    # Patient 1: 34yo female, moderate-severe AD
    patients.append((
        "dupixent-pt-001",
        _bundle([
            _patient_resource("dupixent-pt-001", "Sarah", "Kim", "female", "1991-07-25", "MRN-D001"),
            _condition_resource("L20.9", "Atopic dermatitis, unspecified", onset_date="2016-04-10"),
            _condition_resource("J30.1", "Allergic rhinitis due to pollen", onset_date="2018-03-15"),
            _observation_resource("76382-5", "EASI score", 28.0, "score", effective_date="2025-11-05"),
            _medication_resource("795346", "Triamcinolone acetonide 0.1% topical cream", authored_on="2020-05-20"),
            _medication_resource("372048", "Tacrolimus 0.1% topical ointment", authored_on="2022-09-14"),
        ]),
    ))

    # Patient 2: 28yo male, long-standing AD
    patients.append((
        "dupixent-pt-002",
        _bundle([
            _patient_resource("dupixent-pt-002", "David", "Nguyen", "male", "1997-02-11", "MRN-D002"),
            _condition_resource("L20.89", "Other atopic dermatitis", onset_date="2010-08-20"),
            _condition_resource("L20.9", "Atopic dermatitis, unspecified", onset_date="2010-08-20"),
            _condition_resource("J45.20", "Mild intermittent asthma, uncomplicated", onset_date="2015-06-30"),
            _observation_resource("76382-5", "EASI score", 35.0, "score", effective_date="2025-10-18"),
            _observation_resource("4548-4", "Hemoglobin A1c", 5.4, "%", effective_date="2025-10-18"),
            _medication_resource("197446", "Fluticasone propionate 0.05% topical cream", authored_on="2019-02-28"),
        ]),
    ))

    # Patient 3: 42yo female, failed topical therapy
    patients.append((
        "dupixent-pt-003",
        _bundle([
            _patient_resource("dupixent-pt-003", "Jennifer", "Garcia", "female", "1983-09-04", "MRN-D003"),
            _condition_resource("L20.9", "Atopic dermatitis, unspecified", onset_date="2014-11-22"),
            _observation_resource("76382-5", "EASI score", 22.0, "score", effective_date="2025-12-01"),
            _medication_resource("795346", "Triamcinolone acetonide 0.1% topical cream", authored_on="2018-06-10", status="stopped"),
            _medication_resource("372048", "Tacrolimus 0.1% topical ointment", authored_on="2021-01-05", status="stopped"),
            _medication_resource("197446", "Fluticasone propionate 0.05% topical cream", authored_on="2023-03-20"),
        ]),
    ))

    # Patient 4: 51yo male, AD with eczema herpeticum history
    patients.append((
        "dupixent-pt-004",
        _bundle([
            _patient_resource("dupixent-pt-004", "Michael", "Thompson", "male", "1974-06-18", "MRN-D004"),
            _condition_resource("L20.89", "Other atopic dermatitis", onset_date="2012-03-14"),
            _condition_resource("I10", "Essential hypertension", onset_date="2020-11-05"),
            _observation_resource("76382-5", "EASI score", 31.0, "score", effective_date="2025-09-22"),
            _observation_resource("8480-6", "Systolic blood pressure", 134.0, "mmHg", category_code="vital-signs", effective_date="2025-09-22"),
            _medication_resource("795346", "Triamcinolone acetonide 0.1% topical cream", authored_on="2017-08-12"),
        ]),
    ))

    # Patient 5: 23yo female, young adult onset
    patients.append((
        "dupixent-pt-005",
        _bundle([
            _patient_resource("dupixent-pt-005", "Emily", "Robinson", "female", "2002-10-31", "MRN-D005"),
            _condition_resource("L20.9", "Atopic dermatitis, unspecified", onset_date="2020-05-15"),
            _condition_resource("L20.89", "Other atopic dermatitis", onset_date="2020-05-15"),
            _observation_resource("76382-5", "EASI score", 19.0, "score", effective_date="2025-11-28"),
            _medication_resource("197446", "Fluticasone propionate 0.05% topical cream", authored_on="2020-06-01"),
        ]),
    ))

    return patients


def _libtayo_patients() -> list[tuple[str, dict[str, Any]]]:
    """4 Libtayo eligible patients: Cutaneous SCC, no autoimmune disease."""
    patients = []

    # Patient 1: 74yo male, advanced CSCC
    patients.append((
        "libtayo-pt-001",
        _bundle([
            _patient_resource("libtayo-pt-001", "Richard", "Anderson", "male", "1951-04-08", "MRN-L001"),
            _condition_resource("C44.9", "Malignant neoplasm of skin, unspecified", onset_date="2025-03-15"),
            _condition_resource("C44.92", "Squamous cell carcinoma of skin, unspecified", onset_date="2025-03-15"),
            _condition_resource("I10", "Essential hypertension", onset_date="2008-12-01"),
            _observation_resource("8480-6", "Systolic blood pressure", 142.0, "mmHg", category_code="vital-signs", effective_date="2025-10-10"),
            _medication_resource("316672", "Lisinopril 10 MG", authored_on="2009-01-15"),
            _procedure_resource("71388002", "Skin biopsy", system="http://snomed.info/sct", performed_date="2025-03-10"),
        ]),
    ))

    # Patient 2: 68yo female, CSCC with prior surgery
    patients.append((
        "libtayo-pt-002",
        _bundle([
            _patient_resource("libtayo-pt-002", "Patricia", "Moore", "female", "1957-11-29", "MRN-L002"),
            _condition_resource("C44.92", "Squamous cell carcinoma of skin, unspecified", onset_date="2024-12-05"),
            _condition_resource("C44.9", "Malignant neoplasm of skin, unspecified", onset_date="2024-12-05"),
            _condition_resource("E78.5", "Hyperlipidemia, unspecified", onset_date="2016-05-22"),
            _observation_resource("6690-2", "WBC count", 7.2, "10*3/uL", effective_date="2025-10-30"),
            _medication_resource("36567", "Atorvastatin 20 MG", authored_on="2016-06-01"),
            _procedure_resource("177164001", "Mohs micrographic surgery", system="http://snomed.info/sct", performed_date="2025-01-20"),
        ]),
    ))

    # Patient 3: 79yo male, recurrent CSCC
    patients.append((
        "libtayo-pt-003",
        _bundle([
            _patient_resource("libtayo-pt-003", "George", "Taylor", "male", "1946-08-17", "MRN-L003"),
            _condition_resource("C44.9", "Malignant neoplasm of skin, unspecified", onset_date="2024-08-22"),
            _condition_resource("C44.92", "Squamous cell carcinoma of skin, unspecified", onset_date="2024-08-22"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2005-03-14"),
            _observation_resource("4548-4", "Hemoglobin A1c", 6.8, "%", effective_date="2025-08-15"),
            _medication_resource("860975", "Metformin 500 MG", authored_on="2005-04-01"),
            _procedure_resource("71388002", "Skin biopsy", system="http://snomed.info/sct", performed_date="2024-08-20"),
        ]),
    ))

    # Patient 4: 62yo female, locally advanced CSCC
    patients.append((
        "libtayo-pt-004",
        _bundle([
            _patient_resource("libtayo-pt-004", "Linda", "Davis", "female", "1963-01-12", "MRN-L004"),
            _condition_resource("C44.92", "Squamous cell carcinoma of skin, unspecified", onset_date="2025-05-08"),
            _condition_resource("C44.9", "Malignant neoplasm of skin, unspecified", onset_date="2025-05-08"),
            _observation_resource("8480-6", "Systolic blood pressure", 126.0, "mmHg", category_code="vital-signs", effective_date="2025-11-15"),
            _observation_resource("6690-2", "WBC count", 6.8, "10*3/uL", effective_date="2025-11-15"),
            _procedure_resource("71388002", "Skin biopsy", system="http://snomed.info/sct", performed_date="2025-05-05"),
        ]),
    ))

    return patients


def _ineligible_patients() -> list[tuple[str, dict[str, Any]]]:
    """4 ineligible patients who fail exclusion criteria."""
    patients = []

    # Patient 1: DME patient with HbA1c > 12% (EYLEA exclusion)
    patients.append((
        "ineligible-pt-001",
        _bundle([
            _patient_resource("ineligible-pt-001", "Thomas", "Brown", "male", "1958-07-20", "MRN-X001"),
            _condition_resource("E11", "Type 2 diabetes mellitus", onset_date="2008-11-03"),
            _condition_resource("H35.81", "Retinal edema", onset_date="2025-04-12"),
            _condition_resource("E11.311", "Type 2 DM with diabetic retinopathy with macular edema", onset_date="2025-04-12"),
            _observation_resource("4548-4", "Hemoglobin A1c", 13.2, "%", effective_date="2025-09-28"),
            _medication_resource("1373463", "Insulin glargine 100 UNT/ML", authored_on="2014-06-10"),
        ]),
    ))

    # Patient 2: AD patient with active malignancy (Dupixent exclusion - C80.1)
    patients.append((
        "ineligible-pt-002",
        _bundle([
            _patient_resource("ineligible-pt-002", "Susan", "Martinez", "female", "1975-04-15", "MRN-X002"),
            _condition_resource("L20.9", "Atopic dermatitis, unspecified", onset_date="2019-08-10"),
            _condition_resource("C80.1", "Malignant (primary) neoplasm, unspecified", onset_date="2024-11-20"),
            _observation_resource("76382-5", "EASI score", 25.0, "score", effective_date="2025-10-05"),
            _medication_resource("795346", "Triamcinolone acetonide 0.1% topical cream", authored_on="2020-02-14"),
        ]),
    ))

    # Patient 3: CSCC patient with connective tissue disease (Libtayo exclusion - M35.9)
    patients.append((
        "ineligible-pt-003",
        _bundle([
            _patient_resource("ineligible-pt-003", "Charles", "Wilson", "male", "1960-12-28", "MRN-X003"),
            _condition_resource("C44.92", "Squamous cell carcinoma of skin, unspecified", onset_date="2025-02-17"),
            _condition_resource("C44.9", "Malignant neoplasm of skin, unspecified", onset_date="2025-02-17"),
            _condition_resource("M35.9", "Systemic involvement of connective tissue, unspecified", onset_date="2018-05-10"),
            _medication_resource("5521", "Hydroxychloroquine 200 MG", authored_on="2018-06-01"),
        ]),
    ))

    # Patient 4: AD patient with active tuberculosis (Dupixent exclusion - A15)
    patients.append((
        "ineligible-pt-004",
        _bundle([
            _patient_resource("ineligible-pt-004", "Dorothy", "Lee", "female", "1982-09-07", "MRN-X004"),
            _condition_resource("L20.89", "Other atopic dermatitis", onset_date="2017-06-30"),
            _condition_resource("A15", "Respiratory tuberculosis", onset_date="2025-06-15"),
            _observation_resource("76382-5", "EASI score", 20.0, "score", effective_date="2025-08-20"),
            _medication_resource("197446", "Fluticasone propionate 0.05% topical cream", authored_on="2017-08-01"),
        ]),
    ))

    return patients


# =============================================================================
# Main Seed Logic
# =============================================================================


async def seed_trial_patients() -> None:
    """Seed all trial-ready demo patients via FHIR import."""
    logger.info("Starting trial patient seeding...")

    await init_db()

    all_patients = [
        ("EYLEA HD (DME)", _eylea_patients()),
        ("Dupixent (Atopic Dermatitis)", _dupixent_patients()),
        ("Libtayo (CSCC)", _libtayo_patients()),
        ("Ineligible", _ineligible_patients()),
    ]

    total_imported = 0
    total_facts = 0
    total_nodes = 0
    total_edges = 0

    async with FHIRImportService() as fhir_service:
        for category_name, patient_list in all_patients:
            logger.info(f"\n{'='*60}")
            logger.info(f"Category: {category_name} ({len(patient_list)} patients)")
            logger.info(f"{'='*60}")

            for patient_id, bundle in patient_list:
                async with async_session_maker() as session:
                    result = await fhir_service.import_bundle(
                        session=session,
                        bundle=bundle,
                        internal_patient_id=patient_id,
                    )

                    if result.get("success"):
                        conditions = result.get("conditions", 0)
                        medications = result.get("medications", 0)
                        observations = result.get("observations", 0)
                        procedures = result.get("procedures", 0)
                        nodes = result.get("nodes", 0)
                        edges = result.get("edges", 0)
                        fact_count = conditions + medications + observations + procedures

                        total_imported += 1
                        total_facts += fact_count
                        total_nodes += nodes
                        total_edges += edges

                        logger.info(
                            f"  Imported {result.get('patient_name', patient_id)}: "
                            f"{conditions}C/{medications}M/{observations}O/{procedures}P facts, "
                            f"{nodes} nodes, {edges} edges"
                        )
                    else:
                        logger.error(
                            f"  FAILED {patient_id}: {result.get('error', 'unknown')}"
                        )

    logger.info(f"\n{'='*60}")
    logger.info("Seeding Summary")
    logger.info(f"{'='*60}")
    logger.info(f"  Patients imported: {total_imported}")
    logger.info(f"  ClinicalFacts created: {total_facts}")
    logger.info(f"  KG Nodes created: {total_nodes}")
    logger.info(f"  KG Edges created: {total_edges}")
    logger.info(f"{'='*60}")
    logger.info("")
    logger.info("Patient ID mapping:")
    logger.info("  EYLEA HD:    eylea-pt-001 through eylea-pt-005")
    logger.info("  Dupixent:    dupixent-pt-001 through dupixent-pt-005")
    logger.info("  Libtayo:     libtayo-pt-001 through libtayo-pt-004")
    logger.info("  Ineligible:  ineligible-pt-001 through ineligible-pt-004")


async def main() -> None:
    """Main entry point."""
    try:
        await seed_trial_patients()
    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
