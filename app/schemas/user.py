"""
User Schemas

Request and response models for user endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Shared user fields."""

    email: EmailStr
    full_name: str
    institution: str


class UserResponse(UserBase):
    """User response (public-facing)."""

    id: UUID
    role: str
    is_active: bool
    terms_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """User update request (admin)."""

    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    """User self-update request."""

    full_name: Optional[str] = None
    institution: Optional[str] = None
