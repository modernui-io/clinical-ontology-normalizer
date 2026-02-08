"""Pydantic schemas for clinical trial sites."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Site schemas
# ---------------------------------------------------------------------------


class SiteCreate(BaseModel):
    """Schema for creating a new site."""

    name: str = Field(..., description="Site name (e.g., 'Emory Eye Center')")
    site_code: str | None = Field(None, description="Unique site code identifier")
    organization: str | None = Field(None, description="Parent organization")
    address: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str = Field(default="US", description="Country code")


class SiteResponse(BaseModel):
    """Schema for site API responses."""

    id: UUID
    name: str
    site_code: str | None = None
    organization: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SitePatient(BaseModel):
    """Patient summary within a site context."""

    patient_id: str
    patient_name: str | None = None
    site_id: str


class SiteTrialMatch(BaseModel):
    """Per-trial match summary at a site."""

    trial_id: str
    trial_name: str
    matched_patients: int = 0
    matched_patient_ids: list[str] = Field(default_factory=list)


class SiteScreeningSummary(BaseModel):
    """Aggregated screening results for a site."""

    site_id: str
    site_name: str
    total_patients: int = 0
    patients_screened: int = 0
    patients_matched: int = 0
    trial_matches: list[SiteTrialMatch] = Field(default_factory=list)
