"""
Scenario Schemas

Request and response models for scenario endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


class PretextCategory(str, Enum):
    credential_phishing = "credential_phishing"
    business_email_compromise = "business_email_compromise"
    quishing = "quishing"
    spear_phishing = "spear_phishing"
    whaling = "whaling"
    smishing = "smishing"


class CommunicationChannel(str, Enum):
    email = "email"
    sms = "sms"
    internal_chat = "internal_chat"


class Language(str, Enum):
    english = "english"
    russian = "russian"
    kazakh = "kazakh"


class ScenarioBase(BaseModel):
    """Shared scenario fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    target_role: str = Field(..., min_length=1, max_length=100)
    target_department: Optional[str] = Field(None, max_length=100)
    organization_context: Optional[str] = None
    pretext_category: PretextCategory
    pretext_description: Optional[str] = None
    urgency_level: int = Field(default=3, ge=1, le=5)
    communication_channel: CommunicationChannel = CommunicationChannel.email
    language: Language = Language.english


class ScenarioCreate(ScenarioBase):
    """Scenario creation request."""

    pass


class ScenarioUpdate(BaseModel):
    """Scenario update request (all fields optional)."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_role: Optional[str] = Field(None, min_length=1, max_length=100)
    target_department: Optional[str] = Field(None, max_length=100)
    organization_context: Optional[str] = None
    pretext_category: Optional[PretextCategory] = None
    pretext_description: Optional[str] = None
    urgency_level: Optional[int] = Field(None, ge=1, le=5)
    communication_channel: Optional[CommunicationChannel] = None
    language: Optional[Language] = None


class ScenarioResponse(ScenarioBase):
    """Scenario response."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioListResponse(BaseModel):
    """Paginated scenario list."""

    items: list[ScenarioResponse]
    total: int
    page: int
    per_page: int
