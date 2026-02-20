"""
Authentication Schemas

Request and response models for auth endpoints.
"""

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    institution: str = Field(..., min_length=1, max_length=255)
    terms_accepted: bool


class UserLogin(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str
