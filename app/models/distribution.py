"""
Distribution Model

Stores individual email distributions created from bulk generations.
Tracks delivery status, opens, and clicks for each recipient.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DistributionStatus(str, Enum):
    """Enumeration of distribution statuses."""
    PENDING = "pending"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    FAILED = "failed"
    BOUNCED = "bounced"


class Distribution(Base):
    """Represents a single email distribution to a recipient."""

    __tablename__ = "distributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References to parent objects
    bulk_generation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bulk_generations.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    # Recipient information
    recipient_email = Column(String(255), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=True)
    
    # Email content
    subject = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    
    # Tracking information
    status = Column(
        SAEnum(DistributionStatus),
        default=DistributionStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(String(10), default="0", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    bulk_generation = relationship("BulkGeneration")
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<Distribution(id={self.id}, email={self.recipient_email}, status={self.status})>"
