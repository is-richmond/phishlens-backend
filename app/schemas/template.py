"""
Template Schemas

Request and response models for template endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.scenario import PretextCategory
from app.core.validation import (
    sanitize_text,
    sanitize_optional,
    detect_prompt_injection,
)


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

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v)

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_optional(v)

    @field_validator("system_prompt", "user_prompt_skeleton", mode="before")
    @classmethod
    def check_prompt_injection(cls, v: str) -> str:
        """Reject prompts that contain injection / jailbreak patterns."""
        findings = detect_prompt_injection(v)
        if findings:
            raise ValueError(
                f"Prompt contains disallowed injection patterns: {'; '.join(findings)}"
            )
        return v


class TemplateUpdate(BaseModel):
    """Template update request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[PretextCategory] = None
    system_prompt: Optional[str] = None
    user_prompt_skeleton: Optional[str] = None
    is_public: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_optional(v)

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_optional(v)

    @field_validator("system_prompt", "user_prompt_skeleton", mode="before")
    @classmethod
    def check_prompt_injection(cls, v: Optional[str]) -> Optional[str]:
        """Reject prompts that contain injection / jailbreak patterns."""
        if v is None:
            return None
        findings = detect_prompt_injection(v)
        if findings:
            raise ValueError(
                f"Prompt contains disallowed injection patterns: {'; '.join(findings)}"
            )
        return v


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
