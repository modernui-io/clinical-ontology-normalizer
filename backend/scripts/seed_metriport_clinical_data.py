#!/usr/bin/env python3
"""Seed clinical data for Metriport sandbox patients.

The 5 Metriport sandbox patients exist as patient records but have no clinical
data (consolidated queries returned 404 from Metriport's sandbox). This script
fills in realistic clinical data so they can be used in trial matching demos.

Creates two types of data:
1. Structured FHIR data (simulating Metriport delivery): ClinicalFacts + KGNodes/Edges
2. Clinical notes (simulating EHR-side): Documents with Mentions

Patient-Trial Mapping:
- Andreas Brown -> EYLEA HD (DME): T2DM + diabetic macular edema
- Kyla Brown -> LIBERTY ADCHRONOS (Dupixent): moderate-to-severe atopic dermatitis
- Chris Smith -> no trial match: hypertension + hyperlipidemia (screened but not matched)

Idempotent: checks for existing ClinicalFacts before inserting.

Usage:
    cd backend
    uv run python3 -m scripts.seed_metriport_clinical_data
"""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker, init_db  # noqa: E402
from app.models.clinical_fact import ClinicalFact  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.knowledge_graph import KGEdge, KGNode  # noqa: E402
from app.models.mention import Mention, MentionConceptCandidate  # noqa: E402
from app.schemas.base import Assertion, Domain, Experiencer, JobStatus, Temporality  # noqa: E402
from app.schemas.knowledge_graph import EdgeType, NodeType  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

random.seed(42)

NOW = datetime.now(timezone.utc)

# =============================================================================
# Metriport Patient IDs (from sandbox)
# =============================================================================

ANDREAS_BROWN_ID = "metriport-019c3e38-61b4-7b3d-8ebf-bf5be0e08757"
KYLA_BROWN_ID = "metriport-019c3e38-5df6-7c09-b338-e102316bfefa"
CHRIS_SMITH_ID = "metriport-019c3e38-51b0-7f53-8174-ae769b005597"

# =============================================================================
# Clinical Fact Definitions (structured FHIR data simulation)
# =============================================================================

CLINICAL_FACTS: list[dict[str, Any]] = [
    # =========================================================================
    # Andreas Brown — EYLEA HD candidate (DME)
    # =========================================================================
    {
        "patient_id": ANDREAS_BROWN_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 201826,
        "concept_name": "Type 2 diabetes mellitus",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.98,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": ANDREAS_BROWN_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 4174977,
        "concept_name": "Diabetic macular edema",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.97,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": ANDREAS_BROWN_ID,
        "domain": Domain.MEASUREMENT,
        "omop_concept_id": 3004410,
        "concept_name": "Hemoglobin A1c",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.99,
        "value": "8.1",
        "unit": "%",
    },
    {
        "patient_id": ANDREAS_BROWN_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 320128,
        "concept_name": "Essential hypertension",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.96,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": ANDREAS_BROWN_ID,
        "domain": Domain.DRUG,
        "omop_concept_id": 1503297,
        "concept_name": "Metformin 1000 MG Oral Tablet",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.99,
        "value": None,
        "unit": None,
    },
    # =========================================================================
    # Kyla Brown — Dupixent candidate (atopic dermatitis)
    # =========================================================================
    {
        "patient_id": KYLA_BROWN_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 4299544,
        "concept_name": "Atopic dermatitis",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.98,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": KYLA_BROWN_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 257007,
        "concept_name": "Allergic rhinitis",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.95,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": KYLA_BROWN_ID,
        "domain": Domain.MEASUREMENT,
        "omop_concept_id": 40771922,
        "concept_name": "EASI score",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.99,
        "value": "26",
        "unit": "score",
    },
    {
        "patient_id": KYLA_BROWN_ID,
        "domain": Domain.DRUG,
        "omop_concept_id": 903963,
        "concept_name": "Triamcinolone acetonide topical cream",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.97,
        "value": None,
        "unit": None,
    },
    # =========================================================================
    # Chris Smith — no trial match (hypertension + hyperlipidemia)
    # =========================================================================
    {
        "patient_id": CHRIS_SMITH_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 320128,
        "concept_name": "Essential hypertension",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.97,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": CHRIS_SMITH_ID,
        "domain": Domain.CONDITION,
        "omop_concept_id": 432867,
        "concept_name": "Hyperlipidemia",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.96,
        "value": None,
        "unit": None,
    },
    {
        "patient_id": CHRIS_SMITH_ID,
        "domain": Domain.DRUG,
        "omop_concept_id": 1308216,
        "concept_name": "Lisinopril 10 MG Oral Tablet",
        "assertion": Assertion.PRESENT,
        "temporality": Temporality.CURRENT,
        "confidence": 0.99,
        "value": None,
        "unit": None,
    },
]

# =============================================================================
# KG Node Definitions
# =============================================================================

# Map from (patient_id, concept_name) -> node properties for building edges
# Built dynamically during seeding

KG_PATIENT_NODES: list[dict[str, Any]] = [
    {
        "patient_id": ANDREAS_BROWN_ID,
        "node_type": NodeType.PATIENT,
        "label": "Andreas Brown",
        "properties": {
            "gender": "M",
            "birth_date": "1955-01-28",
            "age": 70,
            "source": "metriport_sandbox",
        },
    },
    {
        "patient_id": KYLA_BROWN_ID,
        "node_type": NodeType.PATIENT,
        "label": "Kyla Brown",
        "properties": {
            "gender": "F",
            "birth_date": "1990-06-10",
            "age": 35,
            "source": "metriport_sandbox",
        },
    },
    {
        "patient_id": CHRIS_SMITH_ID,
        "node_type": NodeType.PATIENT,
        "label": "Chris Smith",
        "properties": {
            "gender": "M",
            "birth_date": "1975-08-22",
            "age": 50,
            "source": "metriport_sandbox",
        },
    },
]

# Domain -> (NodeType, EdgeType) mapping
DOMAIN_TO_KG: dict[Domain, tuple[NodeType, EdgeType]] = {
    Domain.CONDITION: (NodeType.CONDITION, EdgeType.HAS_CONDITION),
    Domain.DRUG: (NodeType.DRUG, EdgeType.TAKES_DRUG),
    Domain.MEASUREMENT: (NodeType.MEASUREMENT, EdgeType.HAS_MEASUREMENT),
}

# =============================================================================
# Clinical Note Templates (EHR-side notes with mentions)
# =============================================================================

CLINICAL_NOTES: list[dict[str, Any]] = [
    # --- Andreas Brown: Ophthalmology progress note ---
    {
        "patient_id": ANDREAS_BROWN_ID,
        "note_type": "progress_note",
        "text": (
            "OPHTHALMOLOGY PROGRESS NOTE\n\n"
            "Patient: Andreas Brown\n"
            "DOB: 01/28/1955 | Age: 70 | Sex: Male\n"
            "Date of Visit: 01/06/2026\n\n"
            "CHIEF COMPLAINT:\n"
            "Gradual worsening of central vision in the right eye over the past 3 months.\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "Mr. Brown is a 70-year-old male with a long-standing history of type 2 diabetes mellitus "
            "(diagnosed 2008, HbA1c 8.1%) who presents with progressive blurring of central vision OD. "
            "He reports difficulty reading and recognizing faces at a distance. He has a known history "
            "of diabetic macular edema diagnosed 18 months ago, previously managed with observation. "
            "Current medications include metformin 1000 mg BID and lisinopril 20 mg daily for "
            "essential hypertension.\n\n"
            "OCULAR EXAMINATION:\n"
            "Visual Acuity: OD 20/80 (baseline 20/40 six months ago), OS 20/30\n"
            "IOP: OD 16 mmHg, OS 15 mmHg\n"
            "Anterior Segment: Mild nuclear sclerotic cataracts OU\n"
            "Dilated Fundus Exam:\n"
            "  OD: Moderate non-proliferative diabetic retinopathy with clinically significant "
            "macular edema. Central macular thickness 420 microns on OCT (normal <300). "
            "Hard exudates in a circinate pattern surrounding the fovea.\n"
            "  OS: Mild NPDR, no macular edema.\n\n"
            "ASSESSMENT AND PLAN:\n"
            "1. Diabetic macular edema, right eye - worsening with significant visual decline. "
            "Central subfield thickness has increased from 340 to 420 microns over 6 months. "
            "Patient meets criteria for anti-VEGF therapy.\n"
            "2. Non-proliferative diabetic retinopathy, bilateral - stable.\n"
            "3. Type 2 diabetes mellitus - suboptimal glycemic control with HbA1c 8.1%. "
            "Recommend endocrinology referral for medication optimization.\n\n"
            "Plan: Initiate intravitreal anti-VEGF injection series OD. "
            "Patient is a candidate for clinical trial enrollment. "
            "Follow-up in 4 weeks with repeat OCT."
        ),
        "mentions": [
            {
                "text": "type 2 diabetes mellitus",
                "section": "HPI",
                "omop_id": 201826,
                "concept_name": "Type 2 diabetes mellitus",
                "concept_code": "E11",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "diabetic macular edema",
                "section": "HPI",
                "omop_id": 4174977,
                "concept_name": "Diabetic macular edema",
                "concept_code": "H35.81",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "metformin 1000 mg",
                "section": "HPI",
                "omop_id": 1503297,
                "concept_name": "Metformin 1000 MG Oral Tablet",
                "concept_code": "861004",
                "vocab": "RxNorm",
                "domain": Domain.DRUG,
            },
            {
                "text": "essential hypertension",
                "section": "HPI",
                "omop_id": 320128,
                "concept_name": "Essential hypertension",
                "concept_code": "I10",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "non-proliferative diabetic retinopathy",
                "section": "EXAM",
                "omop_id": 4216135,
                "concept_name": "Non-proliferative diabetic retinopathy",
                "concept_code": "H35.329",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "anti-VEGF therapy",
                "section": "PLAN",
                "omop_id": 793143,
                "concept_name": "Anti-VEGF injection",
                "concept_code": "67028",
                "vocab": "CPT4",
                "domain": Domain.PROCEDURE,
            },
        ],
    },
    # --- Kyla Brown: Dermatology progress note ---
    {
        "patient_id": KYLA_BROWN_ID,
        "note_type": "progress_note",
        "text": (
            "DERMATOLOGY PROGRESS NOTE\n\n"
            "Patient: Kyla Brown\n"
            "DOB: 06/10/1990 | Age: 35 | Sex: Female\n"
            "Date of Visit: 01/08/2026\n\n"
            "CHIEF COMPLAINT:\n"
            "Worsening atopic dermatitis unresponsive to current topical therapy.\n\n"
            "HISTORY OF PRESENT ILLNESS:\n"
            "Ms. Brown is a 35-year-old female with a lifelong history of atopic dermatitis, "
            "first diagnosed in childhood. She has comorbid allergic rhinitis and a history of "
            "food allergies (peanut, shellfish). Over the past 6 months, her eczema has "
            "significantly worsened despite adherence to a regimen of triamcinolone acetonide "
            "0.1% cream BID to affected areas, daily emollients, and avoidance of known triggers. "
            "She reports involvement of the antecubital fossae, popliteal fossae, neck, and hands "
            "with constant pruritus affecting sleep quality. She has tried and failed topical "
            "tacrolimus 0.1% ointment and a 2-week course of oral prednisone with only transient "
            "improvement.\n\n"
            "SKIN EXAMINATION:\n"
            "Widespread erythematous, lichenified, and excoriated plaques involving:\n"
            "- Bilateral antecubital and popliteal fossae (severe)\n"
            "- Posterior neck and upper back (moderate)\n"
            "- Dorsal hands with fissuring (moderate-to-severe)\n"
            "- Periorbital erythema and mild edema\n\n"
            "Body Surface Area involved: approximately 28%\n"
            "EASI Score: 26 (moderate-to-severe)\n"
            "DLQI: 19 (very large effect on quality of life)\n"
            "IGA: 4 (severe)\n\n"
            "ASSESSMENT AND PLAN:\n"
            "1. Moderate-to-severe atopic dermatitis - inadequate response to topical therapy "
            "including corticosteroids and calcineurin inhibitors. Patient meets criteria for "
            "systemic biologic therapy.\n"
            "2. Allergic rhinitis - stable on cetirizine.\n\n"
            "Plan: Patient is an excellent candidate for dupilumab (anti-IL-4/IL-13) therapy. "
            "Discussed benefits, risks, and the option of clinical trial enrollment for extended "
            "duration biologic studies. Patient interested in trial participation. "
            "Screening labs ordered: CBC, CMP, IgE level, eosinophil count. "
            "Follow-up in 2 weeks to review results and initiate therapy."
        ),
        "mentions": [
            {
                "text": "atopic dermatitis",
                "section": "HPI",
                "omop_id": 4299544,
                "concept_name": "Atopic dermatitis",
                "concept_code": "L20.9",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "allergic rhinitis",
                "section": "HPI",
                "omop_id": 257007,
                "concept_name": "Allergic rhinitis",
                "concept_code": "J30.1",
                "vocab": "ICD10CM",
                "domain": Domain.CONDITION,
            },
            {
                "text": "triamcinolone acetonide",
                "section": "HPI",
                "omop_id": 903963,
                "concept_name": "Triamcinolone acetonide topical cream",
                "concept_code": "10120",
                "vocab": "RxNorm",
                "domain": Domain.DRUG,
            },
            {
                "text": "tacrolimus",
                "section": "HPI",
                "omop_id": 950637,
                "concept_name": "Tacrolimus topical ointment",
                "concept_code": "68139",
                "vocab": "RxNorm",
                "domain": Domain.DRUG,
            },
            {
                "text": "EASI Score: 26",
                "section": "EXAM",
                "omop_id": 40771922,
                "concept_name": "EASI score",
                "concept_code": "76382-5",
                "vocab": "LOINC",
                "domain": Domain.MEASUREMENT,
            },
            {
                "text": "dupilumab",
                "section": "PLAN",
                "omop_id": 1594148,
                "concept_name": "Dupilumab",
                "concept_code": "1876366",
                "vocab": "RxNorm",
                "domain": Domain.DRUG,
            },
        ],
    },
]

# =============================================================================
# Seeding Functions
# =============================================================================


async def check_existing_data() -> bool:
    """Check if Metriport trial-specific clinical data already exists.

    Checks for our specific trial-relevant concept (Diabetic macular edema)
    to distinguish from generic Synthea data that may already exist.
    """
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(
            select(ClinicalFact.id)
            .where(
                ClinicalFact.patient_id == ANDREAS_BROWN_ID,
                ClinicalFact.concept_name == "Diabetic macular edema",
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


async def seed_clinical_facts() -> int:
    """Seed ClinicalFact records for Metriport patients. Returns count.

    Uses raw INSERT to avoid ORM including columns that exist in the model
    but not yet in the DB (e.g. pipeline_version).
    """
    from sqlalchemy import text

    count = 0
    async with async_session_maker() as session:
        for fact_def in CLINICAL_FACTS:
            await session.execute(
                text(
                    "INSERT INTO clinical_facts "
                    "(id, patient_id, domain, omop_concept_id, concept_name, "
                    "assertion, temporality, experiencer, confidence, value, unit, start_date) "
                    "VALUES (:id, :patient_id, :domain, :omop_concept_id, :concept_name, "
                    ":assertion, :temporality, :experiencer, :confidence, :value, :unit, :start_date)"
                ),
                {
                    "id": str(uuid4()),
                    "patient_id": fact_def["patient_id"],
                    "domain": fact_def["domain"].value,
                    "omop_concept_id": fact_def["omop_concept_id"],
                    "concept_name": fact_def["concept_name"],
                    "assertion": fact_def["assertion"].value,
                    "temporality": fact_def["temporality"].value,
                    "experiencer": Experiencer.PATIENT.value,
                    "confidence": fact_def["confidence"],
                    "value": fact_def["value"],
                    "unit": fact_def["unit"],
                    "start_date": NOW - timedelta(days=random.randint(30, 365)),
                },
            )
            count += 1

        await session.commit()

    logger.info(f"  Seeded {count} ClinicalFacts")
    return count


async def seed_kg_nodes_and_edges() -> tuple[int, int]:
    """Seed KGNode and KGEdge records. Returns (node_count, edge_count)."""
    node_count = 0
    edge_count = 0

    async with async_session_maker() as session:
        # Track patient node IDs for edge creation
        patient_node_ids: dict[str, str] = {}

        # Create patient nodes
        for pn_def in KG_PATIENT_NODES:
            node_id = str(uuid4())
            node = KGNode(
                id=node_id,
                patient_id=pn_def["patient_id"],
                node_type=pn_def["node_type"],
                omop_concept_id=None,
                label=pn_def["label"],
                properties=pn_def["properties"],
            )
            session.add(node)
            patient_node_ids[pn_def["patient_id"]] = node_id
            node_count += 1

        # Create concept nodes and edges from clinical facts
        for fact_def in CLINICAL_FACTS:
            patient_id = fact_def["patient_id"]
            domain = fact_def["domain"]

            if domain not in DOMAIN_TO_KG:
                continue

            node_type, edge_type = DOMAIN_TO_KG[domain]

            # Build node properties
            node_props: dict[str, Any] = {
                "assertion": fact_def["assertion"].value,
                "source": "metriport_seed",
            }
            if fact_def["value"] is not None:
                node_props["value"] = fact_def["value"]
            if fact_def["unit"] is not None:
                node_props["unit"] = fact_def["unit"]

            # Create concept node
            concept_node_id = str(uuid4())
            concept_node = KGNode(
                id=concept_node_id,
                patient_id=patient_id,
                node_type=node_type,
                omop_concept_id=fact_def["omop_concept_id"],
                label=fact_def["concept_name"],
                properties=node_props,
            )
            session.add(concept_node)
            node_count += 1

            # Create edge from patient to concept
            patient_node_id = patient_node_ids.get(patient_id)
            if patient_node_id:
                edge = KGEdge(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    source_node_id=patient_node_id,
                    target_node_id=concept_node_id,
                    edge_type=edge_type,
                    properties={"source": "metriport_seed"},
                    temporality="current",
                    temporal_confidence=0.95,
                )
                session.add(edge)
                edge_count += 1

        await session.commit()

    logger.info(f"  Seeded {node_count} KGNodes and {edge_count} KGEdges")
    return node_count, edge_count


async def seed_documents_and_mentions() -> tuple[int, int, int]:
    """Seed clinical note Documents with Mentions and concept candidates.

    Returns (doc_count, mention_count, candidate_count).
    """
    doc_count = 0
    mention_count = 0
    candidate_count = 0

    for note_def in CLINICAL_NOTES:
        async with async_session_maker() as session:
            doc_id = str(uuid4())
            doc = Document(
                id=doc_id,
                patient_id=note_def["patient_id"],
                note_type=note_def["note_type"],
                text=note_def["text"],
                extra_metadata={
                    "source": "metriport_seed",
                    "note_date": (NOW - timedelta(days=random.randint(1, 30))).isoformat(),
                },
                status=JobStatus.COMPLETED,
                processed_at=NOW - timedelta(days=random.randint(0, 5)),
            )
            session.add(doc)
            doc_count += 1

            full_text = note_def["text"]
            for m_def in note_def["mentions"]:
                mention_text = m_def["text"]
                # Find the actual offset in the document text
                start_offset = full_text.find(mention_text)
                if start_offset == -1:
                    # Try case-insensitive search
                    lower_text = full_text.lower()
                    start_offset = lower_text.find(mention_text.lower())
                if start_offset == -1:
                    logger.warning(
                        f"  Could not find mention '{mention_text}' in document "
                        f"for {note_def['patient_id']}"
                    )
                    continue

                end_offset = start_offset + len(mention_text)
                mention_id = str(uuid4())

                mention = Mention(
                    id=mention_id,
                    document_id=doc_id,
                    text=mention_text,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    lexical_variant=mention_text.lower(),
                    section=m_def.get("section"),
                    assertion=Assertion.PRESENT,
                    temporality=Temporality.CURRENT,
                    experiencer=Experiencer.PATIENT,
                    confidence=round(random.uniform(0.85, 0.99), 3),
                )
                session.add(mention)
                mention_count += 1

                # Add concept candidate
                candidate = MentionConceptCandidate(
                    id=str(uuid4()),
                    mention_id=mention_id,
                    omop_concept_id=m_def["omop_id"],
                    concept_name=m_def["concept_name"],
                    concept_code=m_def["concept_code"],
                    vocabulary_id=m_def["vocab"],
                    domain_id=m_def["domain"],
                    score=round(random.uniform(0.88, 0.99), 3),
                    method="demo_exact_match",
                    rank=1,
                )
                session.add(candidate)
                candidate_count += 1

            await session.commit()

    logger.info(
        f"  Seeded {doc_count} Documents, {mention_count} Mentions, "
        f"{candidate_count} MentionConceptCandidates"
    )
    return doc_count, mention_count, candidate_count


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    """Seed all Metriport clinical data."""
    logger.info("=== Metriport Clinical Data Seeder ===")

    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"init_db() raised (tables likely already exist): {e}")

    # Idempotency check
    if await check_existing_data():
        logger.info("Metriport clinical data already exists — skipping seed.")
        logger.info("To re-seed, delete existing ClinicalFacts for Metriport patients first.")
        return

    logger.info("Seeding ClinicalFacts (structured FHIR data)...")
    fact_count = await seed_clinical_facts()

    logger.info("Seeding KG Nodes and Edges...")
    node_count, edge_count = await seed_kg_nodes_and_edges()

    logger.info("Seeding Documents and Mentions (clinical notes)...")
    doc_count, mention_count, candidate_count = await seed_documents_and_mentions()

    logger.info("=== Seeding Complete ===")
    logger.info(f"  ClinicalFacts:            {fact_count}")
    logger.info(f"  KG Nodes:                 {node_count}")
    logger.info(f"  KG Edges:                 {edge_count}")
    logger.info(f"  Documents:                {doc_count}")
    logger.info(f"  Mentions:                 {mention_count}")
    logger.info(f"  MentionConceptCandidates: {candidate_count}")
    logger.info("")
    logger.info("Patient data summary:")
    logger.info(f"  Andreas Brown ({ANDREAS_BROWN_ID}): T2DM + DME -> EYLEA HD candidate")
    logger.info(f"  Kyla Brown ({KYLA_BROWN_ID}): Atopic dermatitis -> Dupixent candidate")
    logger.info(f"  Chris Smith ({CHRIS_SMITH_ID}): HTN + HLD -> no trial match")


if __name__ == "__main__":
    asyncio.run(main())
