#!/usr/bin/env python3
"""Seed script to create initial admin user and RBAC configuration.

This script:
1. Initializes default permissions
2. Initializes default roles (admin, provider, biller, viewer)
3. Creates an admin user if it doesn't exist

Usage:
    python3 -m scripts.seed_admin_user

Or from backend directory:
    python3 scripts/seed_admin_user.py
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
from app.models.rbac import User
from app.services.auth import get_auth_service
from app.services.rbac_service import get_rbac_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default admin user configuration
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_NAME = "System Administrator"


async def seed_admin_user() -> None:
    """Seed the database with default RBAC configuration and admin user."""
    logger.info("Starting RBAC and admin user seeding...")

    # Initialize database
    await init_db()

    async with async_session_maker() as db:
        db: AsyncSession

        # Initialize RBAC service
        rbac_service = get_rbac_service()
        auth_service = get_auth_service()

        # Step 1: Initialize default permissions
        logger.info("Initializing default permissions...")
        perm_count = await rbac_service.initialize_default_permissions(db)
        logger.info(f"Created {perm_count} new permissions")

        # Step 2: Initialize default roles
        logger.info("Initializing default roles...")
        role_count = await rbac_service.initialize_default_roles(db)
        logger.info(f"Created {role_count} new roles")

        # Step 3: Check if admin user exists
        logger.info(f"Checking for existing admin user: {ADMIN_EMAIL}")
        stmt = select(User).where(User.email == ADMIN_EMAIL)
        result = await db.execute(stmt)
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            logger.info(f"Admin user already exists: {ADMIN_EMAIL}")
        else:
            # Create admin user
            logger.info(f"Creating admin user: {ADMIN_EMAIL}")
            try:
                admin_user = await auth_service.create_user(
                    db=db,
                    email=ADMIN_EMAIL,
                    password=ADMIN_PASSWORD,
                    name=ADMIN_NAME,
                    role_names=["admin"],
                )
                logger.info(f"Created admin user with ID: {admin_user.id}")
            except ValueError as e:
                logger.error(f"Failed to create admin user: {e}")
                raise

        logger.info("RBAC and admin user seeding complete!")
        logger.info("")
        logger.info("=" * 60)
        logger.info("Admin User Credentials:")
        logger.info(f"  Email:    {ADMIN_EMAIL}")
        logger.info(f"  Password: {ADMIN_PASSWORD}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("IMPORTANT: Change the admin password after first login!")


async def main() -> None:
    """Main entry point."""
    try:
        await seed_admin_user()
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
