#!/usr/bin/env python3
"""Seed script to create a test SMART on FHIR application.

This script creates a test SMART app for development and testing.

Usage:
    python3 -m scripts.seed_smart_app

Or from backend directory:
    python3 scripts/seed_smart_app.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path if running directly
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, init_db
from app.models.smart_app import SMARTApp
from app.services.smart_auth_server import get_smart_auth_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Test SMART app configuration
TEST_APP_NAME = "Test SMART App"
TEST_APP_REDIRECT_URIS = [
    "http://localhost:3000/smart/callback",
    "http://localhost:3001/smart/callback",
]
TEST_APP_SCOPES = [
    "openid",
    "fhirUser",
    "launch",
    "launch/patient",
    "launch/encounter",
    "offline_access",
    "patient/*.read",
    "patient/*.write",
    "patient/Patient.read",
    "patient/Observation.read",
    "patient/Condition.read",
    "patient/MedicationRequest.read",
    "patient/AllergyIntolerance.read",
    "patient/Procedure.read",
    "patient/Encounter.read",
]


async def seed_smart_app() -> None:
    """Seed the database with a test SMART app."""
    logger.info("Starting SMART app seeding...")

    # Initialize database
    await init_db()

    async with async_session_maker() as db:
        db: AsyncSession

        # Check if test app already exists
        stmt = select(SMARTApp).where(SMARTApp.app_name == TEST_APP_NAME)
        result = await db.execute(stmt)
        existing_app = result.scalar_one_or_none()

        if existing_app:
            logger.info(f"Test SMART app already exists: {existing_app.client_id}")
            logger.info("")
            logger.info("=" * 60)
            logger.info("Existing Test SMART App:")
            logger.info(f"  Client ID: {existing_app.client_id}")
            logger.info("  (Client secret was shown at creation time)")
            logger.info("=" * 60)
            return

        # Create test app
        logger.info(f"Creating test SMART app: {TEST_APP_NAME}")

        smart_server = get_smart_auth_server()
        app_result = await smart_server.register_app(
            db=db,
            name=TEST_APP_NAME,
            redirect_uris=TEST_APP_REDIRECT_URIS,
            scopes=TEST_APP_SCOPES,
            grant_types=["authorization_code", "refresh_token"],
            is_confidential=False,  # Public client for testing
        )

        logger.info("SMART app seeding complete!")
        logger.info("")
        logger.info("=" * 60)
        logger.info("Test SMART App Credentials:")
        logger.info(f"  App Name:      {TEST_APP_NAME}")
        logger.info(f"  Client ID:     {app_result.client_id}")
        if app_result.client_secret:
            logger.info(f"  Client Secret: {app_result.client_secret}")
        else:
            logger.info("  Client Secret: (none - public client)")
        logger.info("")
        logger.info("Redirect URIs:")
        for uri in TEST_APP_REDIRECT_URIS:
            logger.info(f"  - {uri}")
        logger.info("")
        logger.info("Scopes:")
        for scope in TEST_APP_SCOPES:
            logger.info(f"  - {scope}")
        logger.info("=" * 60)


async def main() -> None:
    """Main entry point."""
    try:
        await seed_smart_app()
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
