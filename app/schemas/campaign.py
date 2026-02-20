"""
Campaign Schemas

Request and response models for campaign endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.generation import GenerationResponse


class CampaignBase(BaseModel):
    """Shared campaign fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignCreate(CampaignBase):
    """Campaign creation request."""

    pass


class CampaignUpdate(BaseModel):
    """Campaign update request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignResponse(CampaignBase):
    """Campaign response."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignDetailResponse(CampaignResponse):
    """Campaign with associated generations."""

    generations: list[GenerationResponse] = []
    total_generations: int = 0
    average_score: Optional[float] = None


class CampaignAddGeneration(BaseModel):
    """Request to add a generation to a campaign."""

    generation_id: UUID


class CampaignListResponse(BaseModel):
    """Paginated campaign list."""

    items: list[CampaignResponse]
    total: int
    page: int
    per_page: int
