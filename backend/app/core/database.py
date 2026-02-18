"""Database configuration and session management.

VP-DevOps-3: Added request context logging for database exceptions.

Migration Strategy (VPE-3):
    Schema changes MUST go through Alembic migrations. The migration chain
    lives in backend/alembic/versions/ and is validated by
    backend/scripts/check_migrations.py.

    - Production / Staging: ONLY Alembic manages schema. The init_db()
      function (which calls Base.metadata.create_all) is never invoked.
      Deployments run `alembic upgrade head` via the migrations service
      defined in docker-compose.yml.

    - Development: init_db() may be called when settings.debug is True
      as a convenience to bootstrap a fresh database without running
      migrations. This is acceptable for local development but should
      NOT be relied upon for schema correctness -- always author an
      Alembic migration for any model change.

    - Testing: Tests use create_all() via conftest.py fixtures to spin
      up ephemeral schemas. This is independent of the Alembic chain.

    To validate the migration chain:
        python backend/scripts/check_migrations.py
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Engine, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Request Context for Database Logging
# =============================================================================


@dataclass
class DatabaseRequestContext:
    """Context for database operations, used for logging and debugging.

    This context is propagated through the application using contextvars
    to enable meaningful logging in database operations.
    """

    request_id: str | None = None
    user_id: str | None = None
    endpoint: str | None = None
    method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging extra fields."""
        return {
            k: v for k, v in {
                "request_id": self.request_id,
                "user_id": self.user_id,
                "endpoint": self.endpoint,
                "method": self.method,
            }.items() if v is not None
        }


# Context variable for request context (thread-safe, async-safe)
_db_request_context: ContextVar[DatabaseRequestContext | None] = ContextVar(
    "db_request_context", default=None
)


def get_db_request_context() -> DatabaseRequestContext | None:
    """Get current database request context."""
    return _db_request_context.get()


def set_db_request_context(ctx: DatabaseRequestContext | None) -> None:
    """Set database request context for current async context."""
    _db_request_context.set(ctx)

# Create async engine (for FastAPI async endpoints)
# VP-Platform: Added connection pool configuration for production scalability
# HIPAA §164.312(e): Build connect_args for SSL/TLS transport encryption
_connect_args: dict = {}
if settings.database_ssl_mode != "disable":
    import ssl as _ssl

    _ssl_ctx = _ssl.create_default_context()
    if settings.database_ssl_ca_cert:
        _ssl_ctx.load_verify_locations(settings.database_ssl_ca_cert)
    if settings.database_ssl_mode in ("require",):
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=20,  # Base pool size (default was 5)
    max_overflow=40,  # Additional connections under load (default was 10)
    pool_pre_ping=True,  # Validate connections before use (prevents stale connections)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents timeouts)
    connect_args=_connect_args,
)

# Lazy initialized sync engine (for RQ workers and background jobs)
_sync_engine = None
_sync_engine_lock = threading.Lock()


def get_sync_engine() -> Engine:
    """Get or create sync engine for background jobs.

    Lazily creates the sync engine on first use to avoid import errors
    when psycopg2 is not installed (e.g., in test environments).
    """
    global _sync_engine
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _sync_engine is None:
        with _sync_engine_lock:
            if _sync_engine is None:
                # HIPAA §164.312(e): Build sync connect_args for SSL (psycopg2)
                _sync_connect_args: dict = {}
                if settings.database_ssl_mode != "disable":
                    _sync_connect_args["sslmode"] = settings.database_ssl_mode
                    if settings.database_ssl_ca_cert:
                        _sync_connect_args["sslrootcert"] = settings.database_ssl_ca_cert

                _sync_engine = create_engine(
                    settings.sync_database_url,
                    echo=settings.debug,
                    future=True,
                    pool_size=10,  # Smaller pool for background workers
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args=_sync_connect_args,
                )
    return _sync_engine


# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides common columns and configuration for all models:
    - id: UUID primary key (auto-generated)
    - created_at: Timestamp when record was created
    """

    # Common columns for all models
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """VP-Compliance: Mixin for soft delete pattern.

    Adds deleted_at and deleted_by columns to support:
    - Audit trail for deletions (who deleted what, when)
    - Data recovery (undelete operations)
    - Compliance requirements (retain records for specified periods)

    Usage:
        class Patient(SoftDeleteMixin, Base):
            __tablename__ = "patients"
            ...

    Query examples:
        # Get active records only
        session.query(Patient).filter(Patient.deleted_at.is_(None))

        # Get deleted records
        session.query(Patient).filter(Patient.deleted_at.isnot(None))
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )
    deleted_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self, deleted_by_user_id: str | None = None) -> None:
        """Mark record as deleted without removing from database.

        Args:
            deleted_by_user_id: UUID of user performing the deletion
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_user_id

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    VP-DevOps-3: Added request context logging for exceptions.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()

            # Log exception with request context
            ctx = get_db_request_context()
            extra = ctx.to_dict() if ctx else {}
            extra["error_type"] = type(e).__name__

            logger.error(
                f"Database transaction failed: {type(e).__name__}: {str(e)[:200]}",
                extra=extra,
                exc_info=True,
            )
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables using SQLAlchemy create_all.

    VPE-3 Migration Safety:
        This function bypasses Alembic and creates tables directly from
        ORM model definitions. It must NEVER run in production or staging
        because it can cause schema drift (tables exist but are not tracked
        in the alembic_version table, and column changes are not applied).

        Allowed environments:
            - development (settings.debug == True and environment != production/staging)
            - testing (TESTING env var or pytest context)

        In production and staging, schema is managed exclusively by
        Alembic migrations (alembic upgrade head).
    """
    if settings.environment.lower() in ("production", "staging"):
        logger.warning(
            "init_db() called in %s environment -- skipping create_all. "
            "Use Alembic migrations instead: 'alembic upgrade head'",
            settings.environment,
        )
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
