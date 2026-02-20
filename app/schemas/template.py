"""
Template Schemas

Request and response models for template endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.scenario import PretextCategory


class TemplateBase(BaseModel):
    """Shared template fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: PretextCategory
    system_prompt: str = Field(..., min_length=10)
    user_prompt_skeleton: str = Field(..., min_length=10)


class TemplateCreate(TemplateBase):
    """Template creation request."""

    is_public: bool = False


class TemplateUpdate(BaseModel):
    """Template update request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[PretextCategory] = None
    system_prompt: Optional[str] = None
    user_prompt_skeleton: Optional[str] = None
    is_public: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """Template response."""

    id: UUID
    user_id: Optional[UUID] = None
    is_predefined: bool
    is_public: bool
    version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Paginated template list."""

    items: list[TemplateResponse]
    total: int
    page: int
    per_page: int
