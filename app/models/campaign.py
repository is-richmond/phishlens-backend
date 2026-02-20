"""
Campaign Model

Organizes generated phishing messages into research campaigns.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


# Association table for many-to-many: Campaign <-> Generation
campaign_generations = Table(
    "campaign_generations",
    Base.metadata,
    Column(
        "campaign_id",
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "generation_id",
        UUID(as_uuid=True),
        ForeignKey("generations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("added_at", DateTime, default=datetime.utcnow),
)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User")
    generations = relationship(
        "Generation", secondary=campaign_generations, backref="campaigns"
    )

    def __repr__(self):
        return f"<Campaign(id={self.id}, name={self.name})>"
