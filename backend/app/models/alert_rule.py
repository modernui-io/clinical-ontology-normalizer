"""SQLAlchemy model for persistent alert rules.

Provides DB-backed storage for clinical alert rules,
replacing the in-memory dict storage in AlertRulesService.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertRuleDB(Base):
    """Persistent clinical alert rule.

    Stores alert rule definitions in the database for persistence
    across server restarts. Links optionally to policy sections.
    """

    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="risk_score",
    )
    conditions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    policy_section_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AlertRuleDB(id={self.id}, name='{self.name}', severity='{self.severity}', enabled={self.enabled})>"
