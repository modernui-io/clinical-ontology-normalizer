#!/usr/bin/env python3
"""Seed Metriport sandbox with pre-defined test patients.

Creates the 5 Metriport sandbox patients that return meaningful clinical data
when consolidated queries are triggered. These patients are hard-coded in
Metriport's sandbox environment:

    1. Jane Smith    (F, 1981-03-15)
    2. Chris Smith   (M, 1975-08-22)
    3. Ollie Brown   (M, 1968-11-03)
    4. Kyla Brown    (F, 1990-06-10)
    5. Andreas Brown (M, 1955-01-28)

After creating each patient, the script triggers:
    - start_consolidated_query() -> webhook delivers FHIR Bundle
    - start_document_query()     -> webhook delivers document notifications

Results arrive asynchronously via the Metriport webhook endpoint
(POST /api/v1/metriport/webhook). Make sure ngrok or another tunnel is
running and the webhook URL is registered in the Metriport dashboard.

Prerequisites:
    - METRIPORT_API_KEY set in .env or environment
    - METRIPORT_FACILITY_ID set in .env or environment
    - Backend running with webhook endpoint accessible

Usage:
    cd backend
    uv run python3 -m scripts.seed_metriport_sandbox

    # Or with explicit env vars:
    METRIPORT_API_KEY=... METRIPORT_FACILITY_ID=... uv run python3 -m scripts.seed_metriport_sandbox
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings  # noqa: E402
from app.services.metriport_service import MetriportService, MetriportError  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =========================================================================
# Metriport Sandbox Patients
# =========================================================================
# These are the 5 pre-defined sandbox patients that return synthetic
# clinical data (conditions, medications, observations, etc.)

SANDBOX_PATIENTS = [
    {
        "firstName": "Jane",
        "lastName": "Smith",
        "dob": "1981-03-15",
        "genderAtBirth": "F",
        "address": [
            {
                "addressLine1": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94105",
                "country": "USA",
            }
        ],
    },
    {
        "firstName": "Chris",
        "lastName": "Smith",
        "dob": "1975-08-22",
        "genderAtBirth": "M",
        "address": [
            {
                "addressLine1": "456 Oak Ave",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94107",
                "country": "USA",
            }
        ],
    },
    {
        "firstName": "Ollie",
        "lastName": "Brown",
        "dob": "1968-11-03",
        "genderAtBirth": "M",
        "address": [
            {
                "addressLine1": "789 Pine Rd",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94109",
                "country": "USA",
            }
        ],
    },
    {
        "firstName": "Kyla",
        "lastName": "Brown",
        "dob": "1990-06-10",
        "genderAtBirth": "F",
        "address": [
            {
                "addressLine1": "321 Elm Blvd",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94110",
                "country": "USA",
            }
        ],
    },
    {
        "firstName": "Andreas",
        "lastName": "Brown",
        "dob": "1955-01-28",
        "genderAtBirth": "M",
        "address": [
            {
                "addressLine1": "654 Cedar Ln",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94112",
                "country": "USA",
            }
        ],
    },
]


async def seed_sandbox() -> dict:
    """Create sandbox patients and trigger queries.

    Returns:
        Dict mapping patient names to their Metriport IDs and query statuses.
    """
    api_key = settings.metriport_api_key
    facility_id = settings.metriport_facility_id

    if not api_key:
        logger.error(
            "METRIPORT_API_KEY not set. Add it to backend/.env or set as env var.\n"
            "Get your sandbox API key from https://dash.metriport.com"
        )
        sys.exit(1)

    if not facility_id:
        logger.error(
            "METRIPORT_FACILITY_ID not set. Add it to backend/.env or set as env var.\n"
            "Create a facility in the Metriport dashboard first."
        )
        sys.exit(1)

    logger.info(f"Metriport base URL: {settings.metriport_base_url}")
    logger.info(f"Facility ID: {facility_id}")

    results = {}

    async with MetriportService() as mp:
        # Verify connectivity by listing the facility
        try:
            fac = await mp.get_facility(facility_id)
            logger.info(f"Connected to Metriport facility: {fac.get('name', 'unknown')}")
        except MetriportError as e:
            logger.error(f"Failed to connect to Metriport: {e}")
            sys.exit(1)

        # Check for existing patients to avoid duplicates
        try:
            existing = await mp.list_patients(facility_id)
            existing_names = {
                f"{p.get('firstName', '')} {p.get('lastName', '')}"
                for p in existing
            }
            logger.info(f"Found {len(existing)} existing patients in facility")
        except MetriportError:
            existing_names = set()

        for patient_data in SANDBOX_PATIENTS:
            name = f"{patient_data['firstName']} {patient_data['lastName']}"

            if name in existing_names:
                logger.info(f"  SKIP {name} (already exists)")
                # Find the existing patient ID
                for p in existing:
                    if p.get("firstName") == patient_data["firstName"] and p.get("lastName") == patient_data["lastName"]:
                        results[name] = {
                            "metriport_id": p["id"],
                            "status": "already_exists",
                        }
                        break
                continue

            try:
                # Create patient
                patient = await mp.create_patient(facility_id, patient_data)
                patient_id = patient["id"]
                logger.info(f"  CREATED {name} -> {patient_id}")

                # Trigger consolidated data query (results arrive via webhook)
                try:
                    consolidated = await mp.start_consolidated_query(patient_id)
                    logger.info(f"    Consolidated query started: {consolidated}")
                except MetriportError as e:
                    logger.warning(f"    Consolidated query failed: {e}")
                    consolidated = {"error": str(e)}

                # Trigger document query (results arrive via webhook)
                try:
                    doc_query = await mp.start_document_query(patient_id, facility_id)
                    logger.info(f"    Document query started: {doc_query}")
                except MetriportError as e:
                    logger.warning(f"    Document query failed: {e}")
                    doc_query = {"error": str(e)}

                results[name] = {
                    "metriport_id": patient_id,
                    "status": "created",
                    "consolidated_query": consolidated,
                    "document_query": doc_query,
                }

            except MetriportError as e:
                logger.error(f"  FAILED {name}: {e}")
                results[name] = {"status": "error", "error": str(e)}

    return results


async def main():
    logger.info("=" * 60)
    logger.info("Metriport Sandbox Patient Seeder")
    logger.info("=" * 60)

    results = await seed_sandbox()

    # Write results to JSON file for reference
    output_path = Path(__file__).parent / "metriport_sandbox_patients.json"
    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "facility_id": settings.metriport_facility_id,
        "base_url": settings.metriport_base_url,
        "patients": results,
    }
    output_path.write_text(json.dumps(output, indent=2, default=str))
    logger.info(f"\nResults written to {output_path}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    created = sum(1 for r in results.values() if r.get("status") == "created")
    skipped = sum(1 for r in results.values() if r.get("status") == "already_exists")
    errors = sum(1 for r in results.values() if r.get("status") == "error")
    logger.info(f"  Created: {created}")
    logger.info(f"  Skipped (existing): {skipped}")
    logger.info(f"  Errors: {errors}")

    for name, info in results.items():
        mid = info.get("metriport_id", "N/A")
        logger.info(f"  {name}: {mid} ({info['status']})")

    logger.info("=" * 60)
    logger.info(
        "Webhook data will arrive asynchronously.\n"
        "Make sure your webhook URL is registered in the Metriport dashboard\n"
        "and the backend is running with the /api/v1/metriport/webhook endpoint."
    )


if __name__ == "__main__":
    asyncio.run(main())
