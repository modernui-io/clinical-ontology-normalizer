#!/usr/bin/env python3
"""Seed demo sites and assign Metriport patients to them.

Creates three demo sites for the Regeneron trial matching demo and assigns
the existing Metriport sandbox patients to their respective sites:

  - Emory Eye Center (Atlanta, GA)       -> Andreas Brown (EYLEA candidate)
  - Columbia Dermatology Associates (NYC) -> Kyla Brown (Dupixent candidate)
  - Mount Sinai Internal Medicine (NYC)   -> Chris Smith (no match)

Idempotent: checks for existing sites by site_code before inserting.

Usage:
    cd backend
    uv run python3 -m scripts.seed_demo_sites
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.database import async_session_maker, init_db  # noqa: E402
from app.models.site import PatientSiteAssignment, Site  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Patient IDs (same as seed_metriport_clinical_data.py)
# =============================================================================

ANDREAS_BROWN_ID = "metriport-019c3e38-61b4-7b3d-8ebf-bf5be0e08757"
KYLA_BROWN_ID = "metriport-019c3e38-5df6-7c09-b338-e102316bfefa"
CHRIS_SMITH_ID = "metriport-019c3e38-51b0-7f53-8174-ae769b005597"


# =============================================================================
# Site Definitions
# =============================================================================

DEMO_SITES = [
    {
        "name": "Emory Eye Center",
        "site_code": "EMORY-EYE-001",
        "organization": "Emory Healthcare",
        "address": "1365-B Clifton Rd NE",
        "city": "Atlanta",
        "state": "GA",
        "country": "US",
        "patients": [ANDREAS_BROWN_ID],
    },
    {
        "name": "Columbia Dermatology Associates",
        "site_code": "COLUMBIA-DERM-001",
        "organization": "Columbia University Irving Medical Center",
        "address": "161 Fort Washington Ave",
        "city": "New York",
        "state": "NY",
        "country": "US",
        "patients": [KYLA_BROWN_ID],
    },
    {
        "name": "Mount Sinai Internal Medicine",
        "site_code": "MSINAI-IM-001",
        "organization": "Icahn School of Medicine at Mount Sinai",
        "address": "1 Gustave L. Levy Place",
        "city": "New York",
        "state": "NY",
        "country": "US",
        "patients": [CHRIS_SMITH_ID],
    },
]


# =============================================================================
# Seeding Functions
# =============================================================================


async def check_existing_sites() -> bool:
    """Check if demo sites already exist."""
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(
            select(Site.id)
            .where(Site.site_code == "EMORY-EYE-001")
            .limit(1)
        )
        return result.scalar_one_or_none() is not None


async def seed_sites_and_assignments() -> tuple[int, int]:
    """Seed sites and patient-site assignments. Returns (site_count, assignment_count)."""
    from sqlalchemy import select

    site_count = 0
    assignment_count = 0

    async with async_session_maker() as session:
        for site_def in DEMO_SITES:
            # Check if site already exists
            existing = await session.execute(
                select(Site.id).where(Site.site_code == site_def["site_code"]).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                logger.info(f"  Site '{site_def['name']}' already exists, skipping")
                continue

            site_id = str(uuid4())
            site = Site(
                id=site_id,
                name=site_def["name"],
                site_code=site_def["site_code"],
                organization=site_def["organization"],
                address=site_def["address"],
                city=site_def["city"],
                state=site_def["state"],
                country=site_def["country"],
            )
            session.add(site)
            site_count += 1

            # Create patient-site assignments
            for patient_id in site_def["patients"]:
                # Check if assignment already exists
                existing_assign = await session.execute(
                    select(PatientSiteAssignment.id)
                    .where(
                        PatientSiteAssignment.patient_id == patient_id,
                        PatientSiteAssignment.site_id == site_id,
                    )
                    .limit(1)
                )
                if existing_assign.scalar_one_or_none() is not None:
                    continue

                assignment = PatientSiteAssignment(
                    id=str(uuid4()),
                    patient_id=patient_id,
                    site_id=site_id,
                )
                session.add(assignment)
                assignment_count += 1

        await session.commit()

    return site_count, assignment_count


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    """Seed demo sites and patient assignments."""
    logger.info("=== Demo Site Seeder ===")

    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"init_db() raised (tables likely already exist): {e}")

    # Idempotency check
    if await check_existing_sites():
        logger.info("Demo sites already exist -- skipping seed.")
        logger.info("To re-seed, delete existing sites first.")
        return

    logger.info("Seeding sites and patient assignments...")
    site_count, assignment_count = await seed_sites_and_assignments()

    logger.info("=== Seeding Complete ===")
    logger.info(f"  Sites created:       {site_count}")
    logger.info(f"  Patient assignments: {assignment_count}")
    logger.info("")
    logger.info("Site-patient mapping:")
    logger.info(f"  Emory Eye Center              -> Andreas Brown ({ANDREAS_BROWN_ID})")
    logger.info(f"  Columbia Dermatology Associates -> Kyla Brown ({KYLA_BROWN_ID})")
    logger.info(f"  Mount Sinai Internal Medicine  -> Chris Smith ({CHRIS_SMITH_ID})")


if __name__ == "__main__":
    asyncio.run(main())
