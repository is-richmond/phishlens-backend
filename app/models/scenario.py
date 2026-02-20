"""
Scenario Model

Stores phishing scenario configurations created by researchers.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Target Configuration
    target_role = Column(String(100), nullable=False)  # e.g., "HR Manager", "C-Level"
    target_department = Column(String(100), nullable=True)
    organization_context = Column(Text, nullable=True)  # Org-specific details for RAG

    # Pretext Configuration
    pretext_category = Column(
        SAEnum(
            "credential_phishing",
            "business_email_compromise",
            "quishing",
            "spear_phishing",
            "whaling",
            "smishing",
            name="pretext_category",
        ),
        nullable=False,
    )
    pretext_description = Column(Text, nullable=True)

    # Parameters
    urgency_level = Column(Integer, nullable=False, default=3)  # 1-5 scale
    communication_channel = Column(
        SAEnum("email", "sms", "internal_chat", name="comm_channel"),
        default="email",
        nullable=False,
    )
    language = Column(
        SAEnum("english", "russian", "kazakh", name="language"),
        default="english",
        nullable=False,
    )

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="scenarios")
    generations = relationship(
        "Generation", back_populates="scenario", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Scenario(id={self.id}, title={self.title})>"
