"""
Distribution Schemas

Pydantic models for Distribution API requests and responses.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.distribution import DistributionStatus


class DistributionBase(BaseModel):
    """Base distribution schema."""
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    body: str


class DistributionCreate(DistributionBase):
    """Schema for creating a distribution."""
    bulk_generation_id: UUID
    campaign_id: Optional[UUID] = None


class DistributionUpdate(BaseModel):
    """Schema for updating distribution status."""
    status: DistributionStatus
    error_message: Optional[str] = None


class DistributionResponse(DistributionBase):
    """Schema for distribution response."""
    id: UUID
    bulk_generation_id: UUID
    campaign_id: Optional[UUID] = None
    status: DistributionStatus
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BulkDistributeRequest(BaseModel):
    """Schema for bulk distribution creation request."""
    campaign_name: Optional[str] = Field(None, description="Name for the created campaign")
    send_immediately: bool = Field(
        default=False, 
        description="If True, send immediately. If False, queue for background sending"
    )


class BulkDistributeResponse(BaseModel):
    """Schema for bulk distribution response."""
    campaign_id: UUID
    distributions_created: int = Field(description="Number of distributions created")
    distributions_pending: int = Field(description="Number pending to send")
    status: str = Field(description="Current status (e.g., 'distributions_created', 'sending', 'completed')")
    message: str = Field(description="Human-readable status message")


class DistributionStatusResponse(BaseModel):
    """Schema for distribution status tracking."""
    id: UUID
    recipient_email: str
    status: DistributionStatus
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CampaignDistributionsResponse(BaseModel):
    """Schema for paginated distribution list."""
    distributions: List[DistributionResponse]
    total: int = Field(description="Total number of distributions")
    pending: int = Field(description="Number of pending distributions")
    sent: int = Field(description="Number of sent distributions")
    opened: int = Field(description="Number of opened distributions")
    failed: int = Field(description="Number of failed distributions")
