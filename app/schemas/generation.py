"""
Generation Schemas

Request and response models for generation endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationCreate(BaseModel):
    """Generation request."""

    scenario_id: UUID
    template_id: Optional[UUID] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=100, le=8192)
    model_variant: str = Field(default="gemini-2.5-flash-lite")


class DimensionalScores(BaseModel):
    """Breakdown of realism evaluation scores."""

    linguistic_naturalness: Optional[float] = Field(None, ge=1.0, le=10.0)
    psychological_triggers: Optional[float] = Field(None, ge=1.0, le=10.0)
    technical_plausibility: Optional[float] = Field(None, ge=1.0, le=10.0)
    contextual_relevance: Optional[float] = Field(None, ge=1.0, le=10.0)


class GenerationResponse(BaseModel):
    """Generation response."""

    id: UUID
    scenario_id: UUID
    template_id: Optional[UUID] = None
    input_parameters: dict
    generated_subject: Optional[str] = None
    generated_text: str
    model_used: str
    overall_score: Optional[float] = None
    dimensional_scores: Optional[DimensionalScores] = None
    evaluation_analysis: Optional[str] = None
    watermark: str
    generation_time_ms: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GenerationListResponse(BaseModel):
    """Paginated generation list."""

    items: list[GenerationResponse]
    total: int
    page: int
    per_page: int
