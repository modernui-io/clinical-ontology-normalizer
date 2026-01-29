"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Engine, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

# Create async engine (for FastAPI async endpoints)
# VP-Platform: Added connection pool configuration for production scalability
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=20,  # Base pool size (default was 5)
    max_overflow=40,  # Additional connections under load (default was 10)
    pool_pre_ping=True,  # Validate connections before use (prevents stale connections)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents timeouts)
)

# Lazy initialized sync engine (for RQ workers and background jobs)
_sync_engine = None


def get_sync_engine() -> Engine:
    """Get or create sync engine for background jobs.

    Lazily creates the sync engine on first use to avoid import errors
    when psycopg2 is not installed (e.g., in test environments).
    """
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.sync_database_url,
            echo=settings.debug,
            future=True,
            pool_size=10,  # Smaller pool for background workers
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
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
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = deleted_by_user_id

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    For development only - use Alembic migrations in production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
